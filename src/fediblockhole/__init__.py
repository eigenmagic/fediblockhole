"""A tool for managing federated Mastodon blocklists
"""

import argparse
import toml
import csv
import requests
import json
import time
import os.path
import sys
import urllib.request as urlr

from importlib.metadata import version
__version__ = version('fediblockhole')

import logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s %(levelname)s %(message)s')

# Max size of a URL-fetched blocklist
URL_BLOCKLIST_MAXSIZE = 1024 ** 3

log = logging.getLogger('fediblock_sync')

CONFIGFILE = "/home/mastodon/etc/admin.conf"

# The relative severity levels of blocks
SEVERITY = {
    'noop': 0,
    'silence': 1,
    'suspend': 2,
}

# Default for 'reject_media' setting for each severity level
REJECT_MEDIA_DEFAULT = {
    'noop': False,
    'silence': True,
    'suspend': True,
}

# Default for 'reject_reports' setting for each severity level
REJECT_REPORTS_DEFAULT = {
    'noop': False,
    'silence': True,
    'suspend': True,
}

# Wait at most this long for a remote server to respond
REQUEST_TIMEOUT=30

def sync_blocklists(conf: dict):
    """Sync instance blocklists from remote sources.

    @param conf: A configuration dictionary
    """
    # Build a dict of blocklists we retrieve from remote sources.
    # We will merge these later using a merge algorithm we choose.

    # Always import these fields
    import_fields = ['domain', 'severity']
    # Add extra import fields if defined in config
    import_fields.extend(conf.import_fields)

    # Always export these fields
    export_fields = ['domain', 'severity']
    # Add extra export fields if defined in config
    export_fields.extend(conf.export_fields)

    blocklists = {}
    # Fetch blocklists from URLs
    if not conf.no_fetch_url:
        log.info("Fetching domain blocks from URLs...")
        for listurl in conf.blocklist_url_sources:
            blocklists[listurl] = []
            with urlr.urlopen(listurl) as fp:
                rawdata = fp.read(URL_BLOCKLIST_MAXSIZE).decode('utf-8')
                reader = csv.DictReader(rawdata.split('\n'))
                for row in reader:
                    # Coerce booleans from string to Python bool
                    for boolkey in ['reject_media', 'reject_reports', 'obfuscate']:
                        if boolkey in row:
                            row[boolkey] = str2bool(row[boolkey])

                    # Remove fields we don't want to import
                    origrow = row.copy()
                    for key in origrow:
                        if key not in import_fields:
                            del row[key]
                    blocklists[listurl].append(row)

            if conf.save_intermediate:
                save_intermediate_blocklist(blocklists[listurl], listurl, conf.savedir, export_fields)

    # Fetch blocklists from remote instances
    if not conf.no_fetch_instance:
        log.info("Fetching domain blocks from instances...")
        for blocklist_src in conf.blocklist_instance_sources:
            domain = blocklist_src['domain']
            admin = blocklist_src.get('admin', False)
            token = blocklist_src.get('token', None)
            blocklists[domain] = fetch_instance_blocklist(domain, token, admin, import_fields)
            if conf.save_intermediate:
                save_intermediate_blocklist(blocklists[domain], domain, conf.savedir, export_fields)

    # Merge blocklists into an update dict
    merged = merge_blocklists(blocklists, conf.mergeplan)
    if conf.blocklist_savefile:
        log.info(f"Saving merged blocklist to {conf.blocklist_savefile}")
        save_blocklist_to_file(merged.values(), conf.blocklist_savefile, export_fields)

    # Push the blocklist to destination instances
    if not conf.no_push_instance:
        log.info("Pushing domain blocks to instances...")
        for dest in conf.blocklist_instance_destinations:
            domain = dest['domain']
            token = dest['token']
            max_followed_severity = dest.get('max_followed_severity', 'silence')
            push_blocklist(token, domain, merged.values(), conf.dryrun, import_fields, max_followed_severity)

def merge_blocklists(blocklists: dict, mergeplan: str='max') -> dict:
    """Merge fetched remote blocklists into a bulk update

    @param mergeplan: An optional method of merging overlapping block definitions
        'max' (the default) uses the highest severity block found
        'min' uses the lowest severity block found
    """
    merged = {}

    for key, blist in blocklists.items():
        log.debug(f"processing blocklist from: {key} ...")
        for newblock in blist:
            domain = newblock['domain']
            # If the domain has two asterisks in it, it's obfuscated
            # and we can't really use it, so skip it and do the next one
            if '*' in domain:
                log.debug(f"Domain '{domain}' is obfuscated. Skipping it.")
                continue

            elif domain in merged:
                log.debug(f"Overlapping block for domain {domain}. Merging...")
                blockdata = apply_mergeplan(merged[domain], newblock, mergeplan)

            else:
                # New block
                blockdata = newblock

            # end if
            log.debug(f"blockdata is: {blockdata}")
            merged[domain] = blockdata
        # end for
    return merged

def apply_mergeplan(oldblock: dict, newblock: dict, mergeplan: str='max') -> dict:
    """Use a mergeplan to decide how to merge two overlapping block definitions
    
    @param oldblock: The existing block definition.
    @param newblock: The new block definition we want to merge in.
    @param mergeplan: How to merge. Choices are 'max', the default, and 'min'.
    """
    # Default to the existing block definition
    blockdata = oldblock.copy()

    # If the public or private comment is different,
    # append it to the existing comment, joined with ', '
    # unless the comment is None or an empty string
    keylist = ['public_comment', 'private_comment']
    for key in keylist:
        try:
            if oldblock[key] not in ['', None] and newblock[key] not in ['', None] and oldblock[key] != newblock[key]:
                log.debug(f"old comment: '{oldblock[key]}'")
                log.debug(f"new comment: '{newblock[key]}'")
                blockdata[key] = ', '.join([oldblock[key], newblock[key]])
        except KeyError:
            log.debug(f"Key '{key}' missing from block definition so cannot compare. Continuing...")
            continue
    
    # How do we override an earlier block definition?
    if mergeplan in ['max', None]:
        # Use the highest block level found (the default)
        log.debug(f"Using 'max' mergeplan.")

        if SEVERITY[newblock['severity']] > SEVERITY[oldblock['severity']]:
            log.debug(f"New block severity is higher. Using that.")
            blockdata['severity'] = newblock['severity']
        
        # If obfuscate is set and is True for the domain in
        # any blocklist then obfuscate is set to True.
        if newblock.get('obfuscate', False):
            blockdata['obfuscate'] = True

    elif mergeplan in ['min']:
        # Use the lowest block level found
        log.debug(f"Using 'min' mergeplan.")

        if SEVERITY[newblock['severity']] < SEVERITY[oldblock['severity']]:
            blockdata['severity'] = newblock['severity']

        # If obfuscate is set and is False for the domain in
        # any blocklist then obfuscate is set to False.
        if not newblock.get('obfuscate', True):
            blockdata['obfuscate'] = False

    else:
        raise NotImplementedError(f"Mergeplan '{mergeplan}' not implemented.")

    log.debug(f"Block severity set to {blockdata['severity']}")

    return blockdata

def requests_headers(token: str=None):
    """Set common headers for requests"""
    headers = {
        'User-Agent': f"FediBlockHole/{__version__}"
    }
    if token:
        headers['Authorization'] = f"Bearer {token}"

    return headers

def fetch_instance_blocklist(host: str, token: str=None, admin: bool=False,
    import_fields: list=['domain', 'severity']) -> list:
    """Fetch existing block list from server

    @param host: The remote host to connect to.
    @param token: The (optional) OAuth Bearer token to authenticate with.
    @param admin: Boolean flag to use the admin API if True.
    @param import_fields: A list of fields to import from the remote instance.
    @returns: A list of the domain blocks from the instance.
    """
    log.info(f"Fetching instance blocklist from {host} ...")

    if admin:
        api_path = "/api/v1/admin/domain_blocks"
    else:
        api_path = "/api/v1/instance/domain_blocks"

    headers = requests_headers(token)

    url = f"https://{host}{api_path}"

    domain_blocks = []
    link = True

    while link:
        response = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
        if response.status_code != 200:
            log.error(f"Cannot fetch remote blocklist: {response.content}")
            raise ValueError("Unable to fetch domain block list: %s", response)

        domain_blocks.extend(json.loads(response.content))
        
        # Parse the link header to find the next url to fetch
        # This is a weird and janky way of doing pagination but
        # hey nothing we can do about it we just have to deal
        link = response.headers.get('Link', None)
        if link is None:
            break
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
    # Remove fields not in import list.
    for row in domain_blocks:
        origrow = row.copy()
        for key in origrow:
            if key not in import_fields:
                del row[key]

    return domain_blocks

def delete_block(token: str, host: str, id: int):
    """Remove a domain block"""
    log.debug(f"Removing domain block {id} at {host}...")
    api_path = "/api/v1/admin/domain_blocks/"

    url = f"https://{host}{api_path}{id}"

    response = requests.delete(url,
        headers=requests_headers(token),
        timeout=REQUEST_TIMEOUT
    )
    if response.status_code != 200:
        if response.status_code == 404:
            log.warning(f"No such domain block: {id}")
            return

        raise ValueError(f"Something went wrong: {response.status_code}: {response.content}")

def fetch_instance_follows(token: str, host: str, domain: str) -> int:
    """Fetch the followers of the target domain at the instance

    @param token: the Bearer authentication token for OAuth access
    @param host: the instance API hostname/IP address
    @param domain: the domain to search for followers of
    @returns: int, number of local followers of remote instance accounts
    """
    api_path = "/api/v1/admin/measures"
    url = f"https://{host}{api_path}"

    key = 'instance_follows'

    # This data structure only allows us to request a single domain
    # at a time, which limits the load on the remote instance of each call
    data = {
        'keys': [
            key
            ],
        key: { 'domain': domain },
    }

    # The Mastodon API only accepts JSON formatted POST data for measures
    response = requests.post(url,
        headers=requests_headers(token),
        json=data,
        timeout=REQUEST_TIMEOUT
    )
    if response.status_code != 200:
        if response.status_code == 403:
            log.error(f"Cannot fetch follow information for {domain} from {host}: {response.content}")

        raise ValueError(f"Something went wrong: {response.status_code}: {response.content}")

    # Get the total returned
    follows = int(response.json()[0]['total'])
    return follows

def check_followed_severity(host: str, token: str, domain: str,
    severity: str, max_followed_severity: str='silence'):
    """Check an instance to see if it has followers of a to-be-blocked instance"""

    # If the instance has accounts that follow people on the to-be-blocked domain,
    # limit the maximum severity to the configured `max_followed_severity`.
    follows = fetch_instance_follows(token, host, domain)
    if follows > 0:
        log.debug(f"Instance {host} has {follows} followers of accounts at {domain}.")
        if SEVERITY[severity] > SEVERITY[max_followed_severity]:
            log.warning(f"Instance {host} has {follows} followers of accounts at {domain}. Limiting block severity to {max_followed_severity}.")
            return max_followed_severity
        else:
            return severity

def is_change_needed(oldblock: dict, newblock: dict, import_fields: list):
    """Compare block definitions to see if changes are needed"""
    # Check if anything is actually different and needs updating
    change_needed = []

    for key in import_fields:
        try:
            oldval = oldblock[key]
            newval = newblock[key]
            log.debug(f"Compare {key} '{oldval}' <> '{newval}'")

            if oldval != newval:
                log.debug("Difference detected. Change needed.")
                change_needed.append(key)
                break

        except KeyError:
            log.debug(f"Key '{key}' missing from block definition so cannot compare. Continuing...")
            continue
    
    return change_needed

def update_known_block(token: str, host: str, blockdict: dict):
    """Update an existing domain block with information in blockdict"""
    api_path = "/api/v1/admin/domain_blocks/"

    try:
        id = blockdict['id']
        blockdata = blockdict.copy()
        del blockdata['id']
    except KeyError:
        import pdb
        pdb.set_trace()

    url = f"https://{host}{api_path}{id}"

    response = requests.put(url,
        headers=requests_headers(token),
        data=blockdata,
        timeout=REQUEST_TIMEOUT
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
        headers=requests_headers(token),
        data=blockdata,
        timeout=REQUEST_TIMEOUT
    )
    if response.status_code == 422:
        # A stricter block already exists. Probably for the base domain.
        err = json.loads(response.content)
        log.warning(err['error'])

    elif response.status_code != 200:
            
        raise ValueError(f"Something went wrong: {response.status_code}: {response.content}")
           
def push_blocklist(token: str, host: str, blocklist: list[dict],
                    dryrun: bool=False,
                    import_fields: list=['domain', 'severity'],
                    max_followed_severity='silence',
                    ):
    """Push a blocklist to a remote instance.
    
    Merging the blocklist with the existing list the instance has,
    updating existing entries if they exist.

    @param token: The Bearer token for OAUTH API authentication
    @param host: The instance host, FQDN or IP
    @param blocklist: A list of block definitions. They must include the domain.
    @param import_fields: A list of fields to import to the instances.
    """
    log.info(f"Pushing blocklist to host {host} ...")
    # Fetch the existing blocklist from the instance
    # Force use of the admin API, and add 'id' to the list of fields
    if 'id' not in import_fields:
        import_fields.append('id')
    serverblocks = fetch_instance_blocklist(host, token, True, import_fields)

    # # Convert serverblocks to a dictionary keyed by domain name
    knownblocks = {row['domain']: row for row in serverblocks}

    for newblock in blocklist:

        log.debug(f"Applying newblock: {newblock}")
        oldblock = knownblocks.get(newblock['domain'], None)
        if oldblock:
            log.debug(f"Block already exists for {newblock['domain']}, checking for differences...")

            change_needed = is_change_needed(oldblock, newblock, import_fields)
            
            if change_needed:
                # Change might be needed, but let's see if the severity
                # needs to change. If not, maybe no changes are needed?
                newseverity = check_followed_severity(host, token, oldblock['domain'], newblock['severity'], max_followed_severity)
                if newseverity != oldblock['severity']:
                    newblock['severity'] = newseverity
                    change_needed.append('severity')

                # Change still needed?
                if change_needed:
                    log.info(f"Change detected. Updating domain block for {oldblock['domain']}")
                    blockdata = oldblock.copy()
                    blockdata.update(newblock)
                    if not dryrun:
                        update_known_block(token, host, blockdata)
                        # add a pause here so we don't melt the instance
                        time.sleep(1)
                    else:
                        log.info("Dry run selected. Not applying changes.")

            else:
                log.debug("No differences detected. Not updating.")
                pass

        else:
            # This is a new block for the target instance, so we
            # need to add a block rather than update an existing one
            blockdata = {
                'domain': newblock['domain'],
                # Default to Silence if nothing is specified
                'severity': newblock.get('severity', 'silence'),
                'public_comment': newblock.get('public_comment', ''),
                'private_comment': newblock.get('private_comment', ''),
                'reject_media': newblock.get('reject_media', False),
                'reject_reports': newblock.get('reject_reports', False),
                'obfuscate': newblock.get('obfuscate', False),
            }

            # Make sure the new block doesn't clobber a domain with followers
            blockdata['severity'] = check_followed_severity(host, token, newblock['domain'], max_followed_severity)
            log.info(f"Adding new block for {blockdata['domain']}...")
            if not dryrun:
                add_block(token, host, blockdata)
                # add a pause here so we don't melt the instance
                time.sleep(1)
            else:
                log.info("Dry run selected. Not adding block.")

def load_config(configfile: str):
    """Augment commandline arguments with config file parameters
    
    Config file is expected to be in TOML format
    """
    conf = toml.load(configfile)
    return conf

def save_intermediate_blocklist(
    blocklist: list[dict], source: str,
    filedir: str,
    export_fields: list=['domain','severity']):
    """Save a local copy of a blocklist we've downloaded
    """
    # Invent a filename based on the remote source
    # If the source was a URL, convert it to something less messy
    # If the source was a remote domain, just use the name of the domain
    log.debug(f"Saving intermediate blocklist from {source}")
    source = source.replace('/','-')
    filename = f"{source}.csv"
    filepath = os.path.join(filedir, filename)
    save_blocklist_to_file(blocklist, filepath, export_fields)

def save_blocklist_to_file(
    blocklist: list[dict],
    filepath: str,
    export_fields: list=['domain','severity']):
    """Save a blocklist we've downloaded from a remote source

    @param blocklist: A dictionary of block definitions, keyed by domain
    @param filepath: The path to the file the list should be saved in.
    @param export_fields: Which fields to include in the export.
    """
    try:
        blocklist = sorted(blocklist, key=lambda x: x['domain'])
    except KeyError:
        log.error("Field 'domain' not found in blocklist. Are you sure the URLs are correct?")
        log.debug(f"blocklist is: {blocklist}")

    log.debug(f"export fields: {export_fields}")

    with open(filepath, "w") as fp:
        writer = csv.DictWriter(fp, export_fields, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(blocklist)

def augment_args(args):
    """Augment commandline arguments with config file parameters"""
    conf = toml.load(args.config)

    if not args.no_fetch_url:
        args.no_fetch_url = conf.get('no_fetch_url', False)

    if not args.no_fetch_instance:
        args.no_fetch_instance = conf.get('no_fetch_instance', False)

    if not args.no_push_instance:
        args.no_push_instance = conf.get('no_push_instance', False)

    if not args.blocklist_savefile:
        args.blocklist_savefile = conf.get('blocklist_savefile', None)

    if not args.save_intermediate:
        args.save_intermediate = conf.get('save_intermediate', False)
    
    if not args.savedir:
        args.savedir = conf.get('savedir', '/tmp')

    if not args.export_fields:
        args.export_fields = conf.get('export_fields', [])

    if not args.import_fields:
        args.import_fields = conf.get('import_fields', [])

    args.blocklist_url_sources = conf.get('blocklist_url_sources')
    args.blocklist_instance_sources = conf.get('blocklist_instance_sources')
    args.blocklist_instance_destinations = conf.get('blocklist_instance_destinations')

    return args

def str2bool(boolstring: str) -> bool:
    """Helper function to convert boolean strings to actual Python bools
    """
    boolstring = boolstring.lower()
    if boolstring in ['true', 't', '1', 'y', 'yes']:
        return True
    elif boolstring in ['false', 'f', '0', 'n', 'no']:
        return False
    else:
        raise ValueError(f"Cannot parse value '{boolstring}' as boolean")

def main():

    ap = argparse.ArgumentParser(
        description="Bulk blocklist tool",
        epilog=f"Part of FediBlockHole v{__version__}",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    ap.add_argument('-c', '--config', default='/etc/default/fediblockhole.conf.toml', help="Config file")
    ap.add_argument('-V', '--version', action='store_true', help="Show version and exit.")

    ap.add_argument('-o', '--outfile', dest="blocklist_savefile", help="Save merged blocklist to a local file.")
    ap.add_argument('-S', '--save-intermediate', dest="save_intermediate", action='store_true', help="Save intermediate blocklists we fetch to local files.")
    ap.add_argument('-D', '--savedir', dest="savedir", help="Directory path to save intermediate lists.")
    ap.add_argument('-m', '--mergeplan', choices=['min', 'max'], default='max', help="Set mergeplan.")

    ap.add_argument('-I', '--import-field', dest='import_fields', action='append', help="Extra blocklist fields to import.")
    ap.add_argument('-E', '--export-field', dest='export_fields', action='append', help="Extra blocklist fields to export.")

    ap.add_argument('--no-fetch-url', dest='no_fetch_url', action='store_true', help="Don't fetch from URLs, even if configured.")
    ap.add_argument('--no-fetch-instance', dest='no_fetch_instance', action='store_true', help="Don't fetch from instances, even if configured.")
    ap.add_argument('--no-push-instance', dest='no_push_instance', action='store_true', help="Don't push to instances, even if configured.")

    ap.add_argument('--loglevel', choices=['debug', 'info', 'warning', 'error', 'critical'], help="Set log output level.")
    ap.add_argument('--dryrun', action='store_true', help="Don't actually push updates, just show what would happen.")

    args = ap.parse_args()
    if args.loglevel is not None:
        levelname = args.loglevel.upper()
        log.setLevel(getattr(logging, levelname))

    if args.version:
        print(f"v{__version__}")
        sys.exit(0)

    # Load the configuration file
    args = augment_args(args)

    # Do the work of syncing
    sync_blocklists(args)
