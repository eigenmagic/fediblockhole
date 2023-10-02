"""A tool for managing federated Mastodon blocklists
"""
from __future__ import annotations
import argparse
import toml
import csv
import requests
import json
import time
import os.path
import sys
import urllib.request as urlr

from .blocklists import Blocklist, BlockAuditList, parse_blocklist
from .const import DomainBlock, BlockSeverity, BlockAudit

from importlib.metadata import version
__version__ = version('fediblockhole')

import logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s %(levelname)s %(message)s')
log = logging.getLogger('fediblockhole')

# Max size of a URL-fetched blocklist
URL_BLOCKLIST_MAXSIZE = 1024 ** 3

# Wait at most this long for a remote server to respond
REQUEST_TIMEOUT = 30

# Time to wait between instance API calls to we don't melt them
# The default Mastodon rate limit is 300 calls per 5 minutes
API_CALL_DELAY = 5 * 60 / 300 # 300 calls per 5 minutes

# We always import the domain and the severity
IMPORT_FIELDS = ['domain', 'severity']

# Allowlists always import these fields
ALLOWLIST_IMPORT_FIELDS = ['domain', 'severity', 'public_comment', 'private_comment', 'reject_media', 'reject_reports', 'obfuscate']

# We always export the domain and the severity
EXPORT_FIELDS = ['domain', 'severity']

def sync_blocklists(conf: argparse.Namespace):
    """Sync instance blocklists from remote sources.

    @param conf: A configuration dictionary
    """
    # Build a dict of blocklists we retrieve from remote sources.
    # We will merge these later using a merge algorithm we choose.

    # Always import these fields
    import_fields = IMPORT_FIELDS
    # Add extra import fields if defined in config
    import_fields.extend(conf.import_fields)

    # Always export these fields
    export_fields = EXPORT_FIELDS
    # Add extra export fields if defined in config
    export_fields.extend(conf.export_fields)

    blocklists = []
    # Fetch blocklists from URLs
    if not conf.no_fetch_url:
        blocklists.extend(fetch_from_urls(conf.blocklist_url_sources,
            import_fields, conf.save_intermediate, conf.savedir, export_fields))

    # Fetch blocklists from remote instances
    if not conf.no_fetch_instance:
        blocklists.extend(fetch_from_instances(conf.blocklist_instance_sources,
            import_fields, conf.save_intermediate, conf.savedir, export_fields))

    # Merge blocklists into an update dict
    merged = merge_blocklists(blocklists, conf.mergeplan, conf.merge_threshold, conf.merge_threshold_type, conf.blocklist_auditfile)

    # Remove items listed in allowlists, if any
    allowlists = fetch_allowlists(conf)
    merged = apply_allowlists(merged, conf, allowlists)

    # Save the final mergelist, if requested
    if conf.blocklist_savefile:
        log.info(f"Saving merged blocklist to {conf.blocklist_savefile}")
        save_blocklist_to_file(merged, conf.blocklist_savefile, export_fields)

    # Push the blocklist to destination instances
    if not conf.no_push_instance:
        log.info("Pushing domain blocks to instances...")
        for dest in conf.blocklist_instance_destinations:
            target = dest['domain']
            token = dest['token']
            scheme = dest.get('scheme', 'https')
            max_followed_severity = BlockSeverity(dest.get('max_followed_severity', 'silence'))
            push_blocklist(token, target, merged, conf.dryrun, import_fields, max_followed_severity, scheme, conf.override_private_comment)

def apply_allowlists(merged: Blocklist, conf: argparse.Namespace, allowlists: dict):
    """Apply allowlists
    """
    # Apply allows specified on the commandline
    for domain in conf.allow_domains:
        log.info(f"'{domain}' allowed by commandline, removing any blocks...")
        if domain in merged.blocks:
            del merged.blocks[domain]

    # Apply allows from URLs lists
    log.info("Removing domains from URL allowlists...")
    for alist in allowlists:
        log.debug(f"Processing allows from '{alist.origin}'...")
        for allowed in alist.blocks.values():
            domain = allowed.domain
            log.debug(f"Removing allowlisted domain '{domain}' from merged list.")
            if domain in merged.blocks:
                del merged.blocks[domain]

    return merged

def fetch_allowlists(conf: argparse.Namespace) -> Blocklist:
    """
    """
    if conf.allowlist_url_sources:
        allowlists = fetch_from_urls(conf.allowlist_url_sources, ALLOWLIST_IMPORT_FIELDS, conf.save_intermediate, conf.savedir)
        return allowlists
    return Blocklist()

def fetch_from_urls(url_sources: dict,
    import_fields: list=IMPORT_FIELDS,
    save_intermediate: bool=False,
    savedir: str=None, export_fields: list=EXPORT_FIELDS) -> dict:
    """Fetch blocklists from URL sources
    @param blocklists: A dict of existing blocklists, keyed by source
    @param url_sources: A dict of configuration info for url sources
    @returns: A dict of blocklists, same as input, but (possibly) modified
    """
    log.info("Fetching domain blocks from URLs...")
    blocklists = []
    for item in url_sources:
        url = item['url']
        # If import fields are provided, they override the global ones passed in
        source_import_fields = item.get('import_fields', None)
        if source_import_fields:
            # Ensure we always use the default fields
            import_fields = IMPORT_FIELDS.extend(source_import_fields)

        max_severity = item.get('max_severity', 'suspend')
        listformat = item.get('format', 'csv')
        with urlr.urlopen(url) as fp:
            rawdata = fp.read(URL_BLOCKLIST_MAXSIZE).decode('utf-8')
            bl = parse_blocklist(rawdata, url, listformat, import_fields, max_severity)
            blocklists.append(bl)
            if save_intermediate:
                save_intermediate_blocklist(bl, savedir, export_fields)
    
    return blocklists

def fetch_from_instances(sources: dict,
    import_fields: list=IMPORT_FIELDS,
    save_intermediate: bool=False,
    savedir: str=None, export_fields: list=EXPORT_FIELDS) -> dict:
    """Fetch blocklists from other instances
    @param blocklists: A dict of existing blocklists, keyed by source
    @param url_sources: A dict of configuration info for url sources
    @returns: A dict of blocklists, same as input, but (possibly) modified
    """
    log.info("Fetching domain blocks from instances...")
    blocklists = []
    for item in sources:
        domain = item['domain']
        admin = item.get('admin', False)
        token = item.get('token', None)
        scheme = item.get('scheme', 'https')
        # itemsrc = f"{scheme}://{domain}/api"

        # If import fields are provided, they override the global ones passed in
        source_import_fields = item.get('import_fields', None)
        if source_import_fields:
            # Ensure we always use the default fields
            import_fields = IMPORT_FIELDS.extend(source_import_fields)

        bl = fetch_instance_blocklist(domain, token, admin, import_fields, scheme)
        blocklists.append(bl)
        if save_intermediate:
            save_intermediate_blocklist(bl, savedir, export_fields)
    return blocklists

def merge_blocklists(blocklists: list[Blocklist], mergeplan: str='max',
    threshold: int=0,
    threshold_type: str='count',
    save_block_audit_file: str=None) -> Blocklist:
    """Merge fetched remote blocklists into a bulk update
    @param blocklists: A dict of lists of DomainBlocks, keyed by source.
        Each value is a list of DomainBlocks
    @param mergeplan: An optional method of merging overlapping block definitions
        'max' (the default) uses the highest severity block found
        'min' uses the lowest severity block found
    @param threshold: An integer used in the threshold mechanism.
        If a domain is not present in this number/pct or more of the blocklists,
        it will not get merged into the final list.
    @param threshold_type: choice of ['count', 'pct']
        If `count`, threshold is met if block is present in `threshold`
        or more blocklists.
        If `pct`, theshold is met if block is present in
        count_of_mentions / number_of_blocklists.
    @param returns: A dict of DomainBlocks keyed by domain
    """
    merged = Blocklist('fediblockhole.merge_blocklists')
    audit = BlockAuditList('fediblockhole.merge_blocklists')

    num_blocklists = len(blocklists)

    # Create a domain keyed list of blocks for each domain
    domain_blocks = {}

    for bl in blocklists:
        for block in bl.values():
            if '*' in block.domain:
                log.debug(f"Domain '{block.domain}' is obfuscated. Skipping it.")
                continue
            elif block.domain in domain_blocks:
                domain_blocks[block.domain].append(block)
            else:
                domain_blocks[block.domain] = [block,]

    # Only merge items if `threshold` is met or exceeded
    for domain in domain_blocks:
        domain_matches_count = len(domain_blocks[domain])
        domain_matches_percent = domain_matches_count / num_blocklists * 100
        if threshold_type == 'count':
            domain_threshold_level = domain_matches_count
        elif threshold_type == 'pct':
            domain_threshold_level = domain_matches_percent
            # log.debug(f"domain threshold level: {domain_threshold_level}")
        else:
            raise ValueError(f"Unsupported threshold type '{threshold_type}'. Supported values are: 'count', 'pct'")

        log.debug(f"Checking if {domain_threshold_level} >= {threshold} for {domain}")
        if domain_threshold_level >= threshold:
            # Add first block in the list to merged
            block = domain_blocks[domain][0]
            log.debug(f"Yes. Merging block: {block}")

            # Merge the others with this record
            for newblock in domain_blocks[domain][1:]:
                block = apply_mergeplan(block, newblock, mergeplan)
            merged.blocks[block.domain] = block

        if save_block_audit_file:
            blockdata:BlockAudit = {
                'domain': domain,
                'count': domain_matches_count, 
                'percent': domain_matches_percent,
            }
            audit.blocks[domain] = blockdata

    if save_block_audit_file:
        log.info(f"Saving audit file to {save_block_audit_file}")
        save_domain_block_audit_to_file(audit, save_block_audit_file)

    return merged

def apply_mergeplan(oldblock: DomainBlock, newblock: DomainBlock, mergeplan: str='max') -> dict:
    """Use a mergeplan to decide how to merge two overlapping block definitions
    
    @param oldblock: The existing block definition.
    @param newblock: The new block definition we want to merge in.
    @param mergeplan: How to merge. Choices are 'max', the default, and 'min'.
    """
    # Default to the existing block definition
    blockdata = oldblock._asdict()

    # Merge comments
    keylist = ['public_comment', 'private_comment']
    for key in keylist:
        try:
            oldcomment = getattr(oldblock, key)
            newcomment = getattr(newblock, key)
            blockdata[key] = merge_comments(oldcomment, newcomment)
        except KeyError:
            log.debug(f"Key '{key}' missing from block definition so cannot compare. Continuing...")
            continue
    
    # How do we override an earlier block definition?
    if mergeplan in ['max', None]:
        # Use the highest block level found (the default)
        # log.debug(f"Using 'max' mergeplan.")

        if newblock.severity > oldblock.severity:
            # log.debug(f"New block severity is higher. Using that.")
            blockdata['severity'] = newblock.severity
        
        # For 'reject_media', 'reject_reports', and 'obfuscate' if
        # the value is set and is True for the domain in
        # any blocklist then the value is set to True.
        for key in ['reject_media', 'reject_reports', 'obfuscate']:
            newval = getattr(newblock, key)
            if newval == True:
                blockdata[key] = True

    elif mergeplan in ['min']:
        # Use the lowest block level found
        log.debug(f"Using 'min' mergeplan.")

        if newblock.severity < oldblock.severity:
            blockdata['severity'] = newblock.severity

        # For 'reject_media', 'reject_reports', and 'obfuscate' if
        # the value is set and is False for the domain in
        # any blocklist then the value is set to False.
        for key in ['reject_media', 'reject_reports', 'obfuscate']:
            newval = getattr(newblock, key)
            if newval == False:
                blockdata[key] = False

    else:
        raise NotImplementedError(f"Mergeplan '{mergeplan}' not implemented.")

    # log.debug(f"Block severity set to {blockdata['severity']}")

    return DomainBlock(**blockdata)

def merge_comments(oldcomment:str, newcomment:str) -> str:
    """ Merge two comments

    @param oldcomment: The original comment we're merging into
    @param newcomment: The new commment we want to merge in
    @returns: a new str of the merged comment
    """
    # Don't merge if both comments are None or ''
    if oldcomment in ['', None] and newcomment in ['', None]:
        return ''

    # If both comments are the same, or new comment is empty, don't merge
    if oldcomment == newcomment or newcomment in ['', None]:
        return oldcomment

    # If old comment is empty, just return the new one
    if oldcomment in ['', None]:
        return newcomment

    # We want to skip duplicate fragments so we don't end up
    # re-concatenating the same strings every time there's an
    # update, causing the comment to grow without bound.
    # We tokenize the comments, splitting them on ', ', and comparing
    # the tokens, skipping duplicates.
    # This means "boring, lack of moderation, nazis, scrapers" merging
    # with "lack of moderation, scrapers" should result in
    # "boring, lack of moderation, nazis, scrapers"
    old_tokens = oldcomment.split(', ')
    new_tokens = newcomment.split(', ')
    
    # Remove any empty string tokens that we get
    while '' in old_tokens:
        old_tokens.remove('')
    while '' in new_tokens:
        new_tokens.remove('')

    # Remove duplicate tokens
    for token in old_tokens:
        if token in new_tokens:
            new_tokens.remove(token)

    # Combine whatever tokens are left into one set
    tokenset = old_tokens
    tokenset.extend(new_tokens)

    # Return the merged string
    return ', '.join(tokenset)

def requests_headers(token: str=None):
    """Set common headers for requests"""
    headers = {
        'User-Agent': f"FediBlockHole/{__version__}"
    }
    if token:
        headers['Authorization'] = f"Bearer {token}"

    return headers

def fetch_instance_blocklist(host: str, token: str=None, admin: bool=False,
    import_fields: list=['domain', 'severity'],
    scheme: str='https') -> list[DomainBlock]:
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
        parse_format = 'json'
    else:
        api_path = "/api/v1/instance/domain_blocks"
        parse_format = 'mastodon_api_public'

    headers = requests_headers(token)

    url = f"{scheme}://{host}{api_path}"

    blockdata = []
    link = True
    while link:
        response = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
        if response.status_code != 200:
            log.error(f"Cannot fetch remote blocklist: {response.content}")
            raise ValueError("Unable to fetch domain block list: %s", response)

        # Each block of returned data is a JSON list of dicts
        # so we parse them and append them to the fetched list
        # of JSON data we need to parse.

        blockdata.extend(json.loads(response.content.decode('utf-8')))
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
            # prev = pagination[1]
        
            urlstring, rel = next.split('; ')
            url = urlstring.strip('<').rstrip('>')

    blocklist = parse_blocklist(blockdata, url, parse_format, import_fields)

    return blocklist

def delete_block(token: str, host: str, id: int, scheme: str='https'):
    """Remove a domain block"""
    log.debug(f"Removing domain block {id} at {host}...")
    api_path = "/api/v1/admin/domain_blocks/"

    url = f"{scheme}://{host}{api_path}{id}"

    response = requests.delete(url,
        headers=requests_headers(token),
        timeout=REQUEST_TIMEOUT
    )
    if response.status_code != 200:
        if response.status_code == 404:
            log.warning(f"No such domain block: {id}")
            return

        raise ValueError(f"Something went wrong: {response.status_code}: {response.content}")

def fetch_instance_follows(token: str, host: str, domain: str, scheme: str='https') -> int:
    """Fetch the followers of the target domain at the instance

    @param token: the Bearer authentication token for OAuth access
    @param host: the instance API hostname/IP address
    @param domain: the domain to search for followers of
    @returns: int, number of local followers of remote instance accounts
    """
    api_path = "/api/v1/admin/measures"
    url = f"{scheme}://{host}{api_path}"

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
    severity: BlockSeverity,
    max_followed_severity: BlockSeverity=BlockSeverity('silence'),
    scheme: str='https'):
    """Check an instance to see if it has followers of a to-be-blocked instance"""

    log.debug("Checking followed severity...")
    # Return straight away if we're not increasing the severity
    if severity <= max_followed_severity:
        return severity

    # If the instance has accounts that follow people on the to-be-blocked domain,
    # limit the maximum severity to the configured `max_followed_severity`.
    log.debug("checking for instance follows...")
    follows = fetch_instance_follows(token, host, domain, scheme)
    time.sleep(API_CALL_DELAY)
    if follows > 0:
        log.debug(f"Instance {host} has {follows} followers of accounts at {domain}.")
        if severity > max_followed_severity:
            log.warning(f"Instance {host} has {follows} followers of accounts at {domain}. Limiting block severity to {max_followed_severity}.")
            return max_followed_severity
    return severity

def is_change_needed(oldblock: dict, newblock: dict, import_fields: list):
    change_needed = oldblock.compare_fields(newblock, import_fields)
    return change_needed

def update_known_block(token: str, host: str, block: DomainBlock, scheme: str='https'):
    """Update an existing domain block with information in blockdict"""
    api_path = "/api/v1/admin/domain_blocks/"

    id = block.id
    blockdata = block._asdict()
    del blockdata['id']

    url = f"{scheme}://{host}{api_path}{id}"

    response = requests.put(url,
        headers=requests_headers(token),
        json=blockdata,
        timeout=REQUEST_TIMEOUT
    )
    if response.status_code != 200:
        raise ValueError(f"Something went wrong: {response.status_code}: {response.content}")

def add_block(token: str, host: str, blockdata: DomainBlock, scheme: str='https'):
    """Block a domain on Mastodon host
    """
    log.debug(f"Adding block entry for {blockdata.domain} at {host}...")
    api_path = "/api/v1/admin/domain_blocks"

    url = f"{scheme}://{host}{api_path}"

    response = requests.post(url,
        headers=requests_headers(token),
        json=blockdata._asdict(),
        timeout=REQUEST_TIMEOUT
    )
    if response.status_code == 422:
        # A stricter block already exists. Probably for the base domain.
        err = json.loads(response.content)
        log.warning(err['error'])

    elif response.status_code != 200:
            
        raise ValueError(f"Something went wrong: {response.status_code}: {response.content}")
           
def push_blocklist(token: str, host: str, blocklist: list[DomainBlock],
                    dryrun: bool=False,
                    import_fields: list=['domain', 'severity'],
                    max_followed_severity:BlockSeverity=BlockSeverity('silence'),
                    scheme: str='https',
                    override_private_comment: str=None
                    ):
    """Push a blocklist to a remote instance.
    
    Updates existing entries if they exist, creates new blocks if they don't.

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
    serverblocks = fetch_instance_blocklist(host, token, True, import_fields, scheme)

    # # Convert serverblocks to a dictionary keyed by domain name
    # knownblocks = {row.domain: row for row in serverblocks}

    for newblock in blocklist.values():

        log.debug(f"Processing block: {newblock}")
        if newblock.domain in serverblocks:
            log.debug(f"Block already exists for {newblock.domain}, checking for differences...")

            oldblock = serverblocks[newblock.domain]

            change_needed = is_change_needed(oldblock, newblock, import_fields)

            # Is the severity changing?
            if 'severity' in change_needed:
                log.debug("Severity change requested, checking...")
                if newblock.severity > oldblock.severity:
                    # Confirm if we really want to change the severity
                    # If we still have followers of the remote domain, we may not
                    # want to go all the way to full suspend, depending on the configuration
                    newseverity = check_followed_severity(host, token, oldblock.domain, newblock.severity, max_followed_severity, scheme)
                    if newseverity != oldblock.severity:
                        newblock.severity = newseverity
                    else:
                        log.info("Keeping severity of block the same to avoid disrupting followers.")
                        change_needed.remove('severity')

            if change_needed:
                log.info(f"Change detected. Need to update {change_needed} for domain block for {oldblock.domain}")
                log.info(f"Old block definition: {oldblock}")
                log.info(f"Pushing new block definition: {newblock}")
                blockdata = oldblock.copy()
                blockdata.update(newblock)
                log.debug(f"Block as dict: {blockdata._asdict()}")

                if not dryrun:
                    update_known_block(token, host, blockdata, scheme)
                    # add a pause here so we don't melt the instance
                    time.sleep(API_CALL_DELAY)
                else:
                    log.info("Dry run selected. Not applying changes.")

            else:
                log.debug("No differences detected. Not updating.")
                pass

        else:
            # stamp this record with a private comment, since we're the ones adding it
            if override_private_comment:
                newblock.private_comment = override_private_comment

            # This is a new block for the target instance, so we
            # need to add a block rather than update an existing one
            log.info(f"Adding new block: {newblock}...")
            log.debug(f"Block as dict: {newblock._asdict()}")

            # Make sure the new block doesn't clobber a domain with followers
            newblock.severity = check_followed_severity(host, token, newblock.domain, newblock.severity, max_followed_severity, scheme)
            if not dryrun:
                add_block(token, host, newblock, scheme)
                # add a pause here so we don't melt the instance
                time.sleep(API_CALL_DELAY)
            else:
                log.info("Dry run selected. Not adding block.")

def load_config(configfile: str):
    """Augment commandline arguments with config file parameters
    
    Config file is expected to be in TOML format
    """
    conf = toml.load(configfile)
    return conf

def save_intermediate_blocklist(blocklist: Blocklist, filedir: str,
    export_fields: list=['domain','severity']):
    """Save a local copy of a blocklist we've downloaded
    """
    # Invent a filename based on the remote source
    # If the source was a URL, convert it to something less messy
    # If the source was a remote domain, just use the name of the domain
    source = blocklist.origin
    log.debug(f"Saving intermediate blocklist from {source}")
    source = source.replace('/','-')
    filename = f"{source}.csv"
    filepath = os.path.join(filedir, filename)
    save_blocklist_to_file(blocklist, filepath, export_fields)

def save_blocklist_to_file(
    blocklist: Blocklist,
    filepath: str,
    export_fields: list=['domain','severity']):
    """Save a blocklist we've downloaded from a remote source

    @param blocklist: A dictionary of block definitions, keyed by domain
    @param filepath: The path to the file the list should be saved in.
    @param export_fields: Which fields to include in the export.
    """
    try:
        sorted_list = sorted(blocklist.blocks.items())
    except KeyError:
        log.error("Field 'domain' not found in blocklist.")
        log.debug(f"blocklist is: {sorted_list}")
    except AttributeError:
        log.error("Attribute error!")
        import pdb
        pdb.set_trace()

    log.debug(f"export fields: {export_fields}")

    with open(filepath, "w") as fp:
        writer = csv.DictWriter(fp, export_fields, extrasaction='ignore')
        writer.writeheader()
        for key, value in sorted_list:
            writer.writerow(value)

def save_domain_block_audit_to_file(
    blocklist: BlockAuditList,
    filepath: str):
    """Save an audit log of domains blocked

    @param blocklist: A dictionary of block definitions, keyed by domain
    @param filepath: The path to the file the list should be saved in.
    """
    export_fields = ['domain', 'count', 'percent']

    try:
        sorted_list = sorted(blocklist.blocks.items())
    except KeyError:
        log.error("Field 'domain' not found in blocklist.")
        log.debug(f"blocklist is: {sorted_list}")
    except AttributeError:
        log.error("Attribute error!")
        import pdb
        pdb.set_trace()

    log.debug("exporting audit file")

    with open(filepath, "w") as fp:
        writer = csv.DictWriter(fp, export_fields, extrasaction='ignore')
        writer.writeheader()
        for key, value in sorted_list:
            writer.writerow(value)

def augment_args(args, tomldata: str=None):
    """Augment commandline arguments with config file parameters
    
    If tomldata is provided, uses that data instead of loading
    from a config file.
    """
    if tomldata:
        conf = toml.loads(tomldata)
    else:
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

    if not args.override_private_comment:
        args.override_private_comment = conf.get('override_private_comment', None)
    
    if not args.savedir:
        args.savedir = conf.get('savedir', '/tmp')

    if not args.blocklist_auditfile:
        args.blocklist_auditfile = conf.get('blocklist_auditfile', None)

    if not args.export_fields:
        args.export_fields = conf.get('export_fields', [])

    if not args.import_fields:
        args.import_fields = conf.get('import_fields', [])

    if not args.mergeplan:
        args.mergeplan = conf.get('mergeplan', 'max')

    if not args.merge_threshold:
        args.merge_threshold = conf.get('merge_threshold', 0)

    if not args.merge_threshold_type:
        args.merge_threshold_type = conf.get('merge_threshold_type', 'count')

    args.blocklist_url_sources = conf.get('blocklist_url_sources', [])
    args.blocklist_instance_sources = conf.get('blocklist_instance_sources', [])
    args.allowlist_url_sources = conf.get('allowlist_url_sources', [])
    args.blocklist_instance_destinations = conf.get('blocklist_instance_destinations', [])

    return args

def setup_argparse():
    """Setup the commandline arguments
    """
    ap = argparse.ArgumentParser(
        description="Bulk blocklist tool",
        epilog=f"Part of FediBlockHole v{__version__}",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    ap.add_argument('-c', '--config', default='/etc/default/fediblockhole.conf.toml', help="Config file")
    ap.add_argument('-V', '--version', action='store_true', help="Show version and exit.")

    ap.add_argument('-o', '--outfile', dest="blocklist_savefile", help="Save merged blocklist to a local file.")
    ap.add_argument('-S', '--save-intermediate', dest="save_intermediate", action='store_true', help="Save intermediate blocklists we fetch to local files.")
    ap.add_argument('-D', '--savedir', dest="savedir", help="Directory path to save intermediate lists.")
    ap.add_argument('-m', '--mergeplan', choices=['min', 'max'], help="Set mergeplan.")
    ap.add_argument('-b', '--block-audit-file', dest="blocklist_auditfile", help="Save blocklist auditfile to this location.")
    ap.add_argument('--merge-threshold', type=int, help="Merge threshold value")
    ap.add_argument('--merge-threshold-type', choices=['count', 'pct'], help="Type of merge threshold to use.")
    ap.add_argument('--override-private-comment', dest='override_private_comment', help="Override private_comment with this string for new blocks when pushing blocklists.")

    ap.add_argument('-I', '--import-field', dest='import_fields', action='append', help="Extra blocklist fields to import.")
    ap.add_argument('-E', '--export-field', dest='export_fields', action='append', help="Extra blocklist fields to export.")
    ap.add_argument('-A', '--allow', dest="allow_domains", action='append', default=[], help="Override any blocks to allow this domain.")

    ap.add_argument('--no-fetch-url', dest='no_fetch_url', action='store_true', help="Don't fetch from URLs, even if configured.")
    ap.add_argument('--no-fetch-instance', dest='no_fetch_instance', action='store_true', help="Don't fetch from instances, even if configured.")
    ap.add_argument('--no-push-instance', dest='no_push_instance', action='store_true', help="Don't push to instances, even if configured.")

    ap.add_argument('--loglevel', choices=['debug', 'info', 'warning', 'error', 'critical'], help="Set log output level.")
    ap.add_argument('--dryrun', action='store_true', help="Don't actually push updates, just show what would happen.")

    return ap

def main():

    ap = setup_argparse()
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
