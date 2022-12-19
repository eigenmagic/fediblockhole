#!/usr/bin/python3
# Export and import blocklists via API

import argparse
import toml
import csv
import requests
import json
import csv
import time

import logging
logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s %(levelname)s %(message)s')
import pprint

log = logging.getLogger('fediblock_sync')

CONFIGFILE = "/home/mastodon/etc/admin.conf"

def sync_blocklists(conf: dict):
    """Sync instance blocklists from remote sources.
    """
    # Build a dict of blocklists we retrieve from remote sources.
    # We will merge these later using a merge algorithm we choose.

    blocklists = {}
    # Fetch blocklists from URLs
    # for listurl in conf.blocklist_csv_sources:
    #     blocklists[listurl] = {}
    #     response = requests.get(url)
    #     log.debug(f"Fetched blocklist CSV file: {response.content}")

    # Fetch blocklists from remote instances
    for blocklist_src in conf['blocklist_instance_sources']:
        domain = blocklist_src['domain']
        token = blocklist_src['token']
        blocklists[domain] = fetch_instance_blocklist(token, domain)

    # Merge blocklists into an update dict
    merged = merge_blocklists(blocklists)

    # log.debug(f"Merged blocklist ready:\n")
    # pprint.pp(merged)

    # Push the blocklist to destination instances
    for dest in conf['blocklist_instance_destinations']:
        domain = dest['domain']
        token = dest['token']
        push_blocklist(token, domain, merged.values())

def merge_blocklists(blocklists: dict, mergeplan: str='max') -> dict:
    """Merge fetched remote blocklists into a bulk update

    @param mergeplan: An optional method of merging overlapping block definitions
        'max' (the default) uses the highest severity block found
        'min' uses the lowest severity block found
    """
    # log.debug(f"Merging blocklists {blocklists} ...")
    # Remote blocklists may have conflicting overlaps. We need to
    # decide whether or not to override earlier entries with later
    # ones or not. How to choose which entry is 'correct'?
    merged = {}

    for key, blist in blocklists.items():
        log.debug(f"Adding blocks from {key} ...")
        for blockdef in blist:
            # log.debug(f"Checking blockdef {blockdef} ...")
            domain = blockdef['domain']
            if domain in merged:
                blockdata = merged[domain]

                # If the public or private comment is different,
                # append it to the existing comment, joined with a newline
                if blockdef['public_comment'] != blockdata['public_comment'] and blockdata['public_comment'] != '':
                    blockdata['public_comment'] = '\n'.join([blockdef['public_comment'], blockdata['public_comment']])

                if blockdef['private_comment'] != blockdata['private_comment'] and blockdata['private_comment'] != '':
                    blockdata['private_comment'] = '\n'.join([blockdef['private_comment'], blockdata['private_comment']])

                # How do we override an earlier block definition?
                if mergeplan in ['max', None]:
                    # Use the highest block level found (the default)
                    if blockdef['severity'] == 'suspend':
                        blockdata['severity'] = 'suspend'

                    if blockdef['reject_media'] == True:
                        blockdata['reject_media'] = True

                    if blockdef['reject_reports'] == True:
                        blockdata['reject_reports'] = True

                elif mergeplan in ['min']:
                    # Use the lowest block level found
                    if blockdef['severity'] == 'silence':
                        blockdata['severity'] = 'silence'

                    if blockdef['reject_media'] == False:
                        blockdata['reject_media'] = False

                    if blockdef['reject_reports'] == False:
                        blockdata['reject_reports'] = False

                else:
                    raise NotImplementedError(f"Mergeplan '{mergeplan}' not implemented.")

            else:
                # New block
                blockdata = {
                    'domain': blockdef['domain'],
                    # Default to Silence if nothing is specified
                    'severity': blockdef.get('severity', 'silence'),
                    'public_comment': blockdef['public_comment'],
                    'private_comment': blockdef['private_comment'],
                    'reject_media': blockdef.get('reject_media', False),
                    'reject_reports': blockdef.get('reject_reports', False),
                    'obfuscate': blockdef.get('obfuscate', False),
                }
            merged[domain] = blockdata

    return merged

def fetch_instance_blocklist(token: str, host: str) -> list:
    """Fetch existing block list from server
    """
    api_path = "/api/v1/admin/domain_blocks"

    url = f"https://{host}{api_path}"

    domain_blocks = []
    link = True

    while link:
        response = requests.get(url, headers={'Authorization': f"Bearer {token}"})
        if response.status_code != 200:
            log.error(f"Cannot fetch remote blocklist: {response.content}")
            raise ValueError("Unable to fetch domain block list: %s", response)
        domain_blocks.extend(json.loads(response.content))
        
        # Parse the link header to find the next url to fetch
        # This is a weird and janky way of doing pagination but
        # hey nothing we can do about it we just have to deal
        link = response.headers['Link']
        pagination = link.split(', ')
        if len(pagination) != 2:
            link = None
            break
        else:
            next = pagination[0]
            prev = pagination[1]
        
            urlstring, rel = next.split('; ')
            url = urlstring.strip('<').rstrip('>')

    log.debug(f"Found {len(domain_blocks)} existing domain blocks.")
    return domain_blocks

def export_blocklist(token: str, host: str, outfile: str):
    """Export current server blocklist to a csv file"""
    blocklist = fetch_instance_blocklist(token, host)
    fieldnames = ['id', 'domain', 'severity', 'reject_media', 'reject_reports', 'private_comment', 'public_comment', 'obfuscate']

    blocklist = sorted(blocklist, key=lambda x: int(x['id']))

    with open(outfile, "w") as fp:
        writer = csv.DictWriter(fp, fieldnames, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(blocklist)

def delete_blocklist(token: str, host: str, blockfile: str):
    """Delete domain blocks listed in blockfile"""
    with open(blockfile) as fp:
        reader = csv.DictReader(fp)
        for row in reader:
            domain = row['domain']
            id = row['id']
            log.debug(f"Deleting {domain} (id: {id}) from blocklist...")
            delete_block(token, host, id)

def delete_block(token: str, host: str, id: int):
    """Remove a domain block"""
    log.debug(f"Removing domain block {id} at {host}...")
    api_path = "/api/v1/admin/domain_blocks/"

    url = f"https://{host}{api_path}{id}"

    response = requests.delete(url,
        headers={'Authorization': f"Bearer {token}"}
    )
    if response.status_code != 200:
        if response.status_code == 404:
            log.warn(f"No such domain block: {id}")
            return

        raise ValueError(f"Something went wrong: {response.status_code}: {response.content}")

def update_known_block(token: str, host: str, blockdict: dict):
    """Update an existing domain block with information in blockdict"""
    api_path = "/api/v1/admin/domain_blocks/"

    id = blockdict['id']
    blockdata = blockdict.copy()
    del blockdata['id']

    url = f"https://{host}{api_path}{id}"

    response = requests.put(url,
        headers={'Authorization': f"Bearer {token}"},
        data=blockdata
    )
    if response.status_code != 200:
        raise ValueError(f"Something went wrong: {response.status_code}: {response.content}")

def add_block(token: str, host: str, blockdata: dict):
    """Block a domain on Mastodon host
    """
    log.debug(f"Blocking domain {blockdata['domain']} at {host}...")
    api_path = "/api/v1/admin/domain_blocks"

    url = f"https://{host}{api_path}"

    response = requests.post(url,
        headers={'Authorization': f"Bearer {token}"},
        data=blockdata
    )
    if response.status_code != 200:
        raise ValueError(f"Something went wrong: {response.status_code}: {response.content}")

def push_blocklist(token: str, host: str, blocklist: list[dict]):
    """Push a blocklist to a remote instance.
    
    Merging the blocklist with the existing list the instance has,
    updating existing entries if they exist.

    @param token: The Bearer token for OAUTH API authentication
    @param host: The instance host, FQDN or IP
    @param blocklist: A list of block definitions. They must include the domain.
    """
    # Fetch the existing blocklist from the instance
    serverblocks = fetch_instance_blocklist(token, host)

    # Convert serverblocks to a dictionary keyed by domain name
    knownblocks = {row['domain']: row for row in serverblocks}

    for row in blocklist:
        # log.debug(f"Importing definition: {row}")

        if 'id' in row: del row['id']

        try:
            blockdict = knownblocks[row['domain']]
            log.info(f"Block already exists for {row['domain']}, merging data...")

            # Check if anything is actually different and needs updating
            change_needed = False
            for key in [
                'severity',
                'public_comment',
                'private_comment',
                'reject_media',
                'reject_reports',
                'obfuscate',
                ]:
                try:
                    if blockdict[key] != knownblocks[key]:
                        change_needed = True
                        break
                except KeyError:
                    break
            
            if change_needed:
                log.debug(f"Change detected. Updating domain block for {row['domain']}")
                blockdict.update(row)
                update_known_block(token, host, blockdict)
                # add a pause here so we don't melt the instance
                time.sleep(1)

            else:
                log.info("No differences detected. Not updating.")

        except KeyError:
            # domain doesn't have an entry, so we need to create one
            blockdata = {
                'domain': row['domain'],
                # Default to Silence if nothing is specified
                'severity': row.get('severity', 'silence'),
                'public_comment': row['public_comment'],
                'private_comment': row['private_comment'],
                'reject_media': row.get('reject_media', False),
                'reject_reports': row.get('reject_reports', False),
                'obfuscate': row.get('obfuscate', False),
            }
            log.info(f"Adding new block for {blockdata['domain']}...")
            add_block(token, host, blockdata)
            # add a pause here so we don't melt the instance
            time.sleep(1)

def load_config(configfile: str):
    """Augment commandline arguments with config file parameters
    
    Config file is expected to be in TOML format
    """
    conf = toml.load(configfile)
    return conf

def save_intermediate(blocklist: list, source: str, filedir: str):
    """Save a blocklist we've downloaded from a remote source

    Save a local copy of the remote blocklist after downloading it.
    """


if __name__ == '__main__':

    ap = argparse.ArgumentParser(description="Bulk blocklist tool",
                                 formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    ap.add_argument('-c', '--config', default='/etc/default/fediblockhole.conf.toml', help="Config file")

    ap.add_argument('--loglevel', choices=['debug', 'info', 'warning', 'error', 'critical'], help="Set log output level.")

    args = ap.parse_args()
    if args.loglevel is not None:
        levelname = args.loglevel.upper()
        log.setLevel(getattr(logging, levelname))

    # Load the configuration file
    conf = load_config(args.config)
    
    # Do the work of syncing
    sync_blocklists(conf)