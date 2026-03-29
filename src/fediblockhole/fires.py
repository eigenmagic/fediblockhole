"""FIRES protocol support for FediBlockHole

Fetches moderation recommendations from FIRES (Fediverse Intelligence
Replication Endpoint Server) datasets and converts them to DomainBlocks
for merging into the standard FediBlockHole pipeline.

FIRES datasets publish snapshots (current state) and changes feeds
(incremental updates with retractions). This module supports both modes:

- First run: fetch the full snapshot
- Subsequent runs: poll the changes feed from the last-seen cursor
- Retractions: remove domains from the source's contribution

State is persisted in a JSON file so we can do incremental polling.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Optional

import requests

from .blocklists import Blocklist
from .const import DomainBlock

log = logging.getLogger("fediblockhole")

# FIRES policy -> Mastodon severity mapping
# 'accept' is handled separately as an allowlist entry
POLICY_MAP = {
    "drop": "suspend",
    "reject": "suspend",
    "filter": "silence",
}

# Policies that indicate the domain should be allowed, not blocked
ALLOW_POLICIES = {"accept"}

# Default state file location
DEFAULT_STATE_FILE = os.path.expanduser("~/.fediblockhole/fires_state.json")

# Request timeout for FIRES API calls
REQUEST_TIMEOUT = 30


class FIRESState:
    """Manages persistent state for FIRES dataset polling.
    
    Tracks the last-seen change cursor per dataset URL so we can
    do incremental polling on subsequent runs.
    """

    def __init__(self, filepath: str = DEFAULT_STATE_FILE):
        self.filepath = filepath
        self.data = self._load()

    def _load(self) -> dict:
        """Load state from disk, or return empty state."""
        if os.path.exists(self.filepath):
            try:
                with open(self.filepath, "r") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                log.warning(f"Could not load FIRES state from {self.filepath}: {e}")
        return {}

    def save(self):
        """Persist state to disk."""
        os.makedirs(os.path.dirname(self.filepath), exist_ok=True)
        with open(self.filepath, "w") as f:
            json.dump(self.data, f, indent=2)

    def get_cursor(self, dataset_url: str) -> Optional[str]:
        """Get the last-seen changes cursor URL for a dataset."""
        return self.data.get(dataset_url, {}).get("cursor")

    def set_cursor(self, dataset_url: str, cursor: str):
        """Update the cursor for a dataset."""
        if dataset_url not in self.data:
            self.data[dataset_url] = {}
        self.data[dataset_url]["cursor"] = cursor

    def get_retractions(self, dataset_url: str) -> set:
        """Get the set of retracted domains for a dataset."""
        return set(self.data.get(dataset_url, {}).get("retractions", []))

    def add_retraction(self, dataset_url: str, domain: str):
        """Record a retraction for a domain."""
        if dataset_url not in self.data:
            self.data[dataset_url] = {}
        retractions = self.data[dataset_url].get("retractions", [])
        if domain not in retractions:
            retractions.append(domain)
        self.data[dataset_url]["retractions"] = retractions

    def remove_retraction(self, dataset_url: str, domain: str):
        """Remove a retraction (domain was re-recommended)."""
        if dataset_url in self.data:
            retractions = self.data[dataset_url].get("retractions", [])
            if domain in retractions:
                retractions.remove(domain)
            self.data[dataset_url]["retractions"] = retractions


class FIRESClient:
    """HTTP client for consuming public FIRES protocol endpoints."""

    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")

    def _headers(self) -> dict:
        return {
            "Accept": "application/ld+json, application/json",
            "User-Agent": "FediBlockHole-FIRES/1.0",
        }

    def _get(self, url: str) -> dict:
        """Fetch a URL and return parsed JSON."""
        log.debug(f"FIRES fetch: {url}")
        response = requests.get(
            url, headers=self._headers(), timeout=REQUEST_TIMEOUT
        )
        if response.status_code != 200:
            log.error(f"FIRES request failed: {response.status_code} {url}")
            raise ValueError(
                f"FIRES request failed: {response.status_code}: {response.content}"
            )
        return response.json()

    def get_datasets(self) -> list:
        """List all datasets on the server."""
        data = self._get(f"{self.base_url}/datasets")
        # The datasets collection uses 'items', not 'orderedItems'
        return data.get("items", data.get("orderedItems", []))

    def get_snapshot(self, dataset_id: str) -> dict:
        """Fetch the current snapshot for a dataset."""
        return self._get(f"{self.base_url}/datasets/{dataset_id}/snapshot")

    def get_changes(self, dataset_id: str, since: str = None) -> dict:
        """Fetch a page of changes for a dataset."""
        url = f"{self.base_url}/datasets/{dataset_id}/changes"
        if since:
            url += f"?since={since}"
        return self._get(url)

    def get_changes_from_url(self, url: str) -> dict:
        """Fetch changes from a full URL (for pagination)."""
        return self._get(url)

    def get_labels(self) -> dict:
        """Fetch the labels collection."""
        return self._get(f"{self.base_url}/labels")


def fires_policy_to_severity(policy: str) -> str:
    """Map a FIRES recommended policy to a Mastodon severity.
    
    drop/reject -> suspend
    filter -> silence
    unknown -> suspend (safe default)
    """
    return POLICY_MAP.get(policy, "suspend")


def fires_labels_to_comment(labels: list, label_names: dict) -> str:
    """Convert FIRES label URLs/IDs to a human-readable comment string.
    
    @param labels: List of label URLs or UUIDs from the FIRES response
    @param label_names: Dict mapping label URL/ID -> human-readable name
    @returns: Comma-separated string of label names
    """
    names = []
    for label_ref in labels:
        if label_ref in label_names:
            names.append(label_names[label_ref])
        else:
            # Try extracting a slug from a URL as fallback
            slug = label_ref.rstrip("/").split("/")[-1]
            names.append(slug)
    return ", ".join(names)


def build_label_map(client: FIRESClient) -> dict:
    """Fetch labels from the FIRES server and build an ID -> name map."""
    label_map = {}
    try:
        labels_data = client.get_labels()
        for item in labels_data.get("items", []):
            label_id = item.get("id", "")
            # Prefer nameMap.en over flat name
            name_map = item.get("nameMap")
            if name_map and isinstance(name_map, dict):
                name = name_map.get("en", name_map.get("en-US", ""))
                if not name:
                    # Grab first available
                    name = next(iter(name_map.values()), "")
            else:
                name = item.get("name", "")
            if label_id and name:
                label_map[label_id] = name
    except Exception as e:
        log.warning(f"Could not fetch FIRES labels: {e}")
    return label_map


def snapshot_to_blocklist(
    snapshot: dict,
    origin: str,
    label_map: dict,
    max_severity: str = "suspend",
    retractions: set = None,
    ignore_accept: bool = False,
) -> tuple:
    """Convert a FIRES snapshot response to a Blocklist and an allowlist.
    
    FIRES recommendations with 'accept' policy become allowlist entries.
    All other recommendations become blocklist entries.
    
    @param snapshot: The parsed JSON snapshot from the FIRES API
    @param origin: Origin string for the blocklist
    @param label_map: Dict mapping label IDs to names
    @param max_severity: Maximum severity to apply
    @param retractions: Set of domains to exclude (previously retracted)
    @returns: Tuple of (Blocklist, Blocklist) where the second is the allowlist
    """
    if retractions is None:
        retractions = set()

    blocklist = Blocklist(origin)
    allowlist = Blocklist(origin)
    items = snapshot.get("orderedItems", [])

    for item in items:
        item_type = item.get("type", "")
        entity_kind = item.get("entityKind", "")
        domain = item.get("entityKey", "")

        # We only handle domain recommendations
        if entity_kind != "domain" or not domain:
            continue

        # Only Recommendations are actionable blocks.
        # Retractions, Advisories, and Tombstones are skipped:
        #   - Retraction: latest action was a retraction, not an active block
        #   - Advisory: informational only, no recommended action
        #   - Tombstone: historical cleanup
        if item_type != "Recommendation":
            continue

        # Skip domains that have been retracted via changes feed
        if domain in retractions:
            continue

        # Map FIRES policy to Mastodon severity
        policy = item.get("recommendedPolicy", "drop")

        # Accept policy -> allowlist (unless ignored)
        if policy in ALLOW_POLICIES:
            if not ignore_accept:
                allowlist.blocks[domain] = DomainBlock(
                    domain=domain,
                    severity="noop",
                    public_comment=fires_labels_to_comment(
                        item.get("labels", []), label_map
                    ),
                )
            continue

        severity = fires_policy_to_severity(policy)

        # Build a comment from labels
        labels = item.get("labels", [])
        public_comment = fires_labels_to_comment(labels, label_map)

        block = DomainBlock(
            domain=domain,
            severity=severity,
            public_comment=public_comment,
        )

        # Apply max_severity cap
        from .const import BlockSeverity
        max_sev = BlockSeverity(max_severity)
        if block.severity > max_sev:
            block.severity = max_sev

        blocklist.blocks[domain] = block

    return blocklist, allowlist


def apply_changes(
    blocklist: Blocklist,
    allowlist: Blocklist,
    changes: list,
    label_map: dict,
    state: FIRESState,
    dataset_url: str,
    max_severity: str = "suspend",
    ignore_accept: bool = False,
) -> tuple:
    """Apply a list of FIRES change items to existing blocklist and allowlist.
    
    Recommendations with accept policy go to the allowlist.
    Other recommendations add/update blocklist entries.
    Retractions remove entries from both lists and record in state.
    
    @param blocklist: The existing blocklist to modify
    @param allowlist: The existing allowlist to modify
    @param changes: List of change items from the FIRES changes feed
    @param label_map: Dict mapping label IDs to names
    @param state: FIRESState for recording retractions
    @param dataset_url: The dataset URL key for state tracking
    @param max_severity: Maximum severity to apply
    @returns: Tuple of (blocklist, allowlist)
    """
    from .const import BlockSeverity

    for item in changes:
        item_type = item.get("type", "")
        entity_kind = item.get("entityKind", "")
        domain = item.get("entityKey", "")

        if entity_kind != "domain" or not domain:
            continue

        if item_type == "Recommendation":
            policy = item.get("recommendedPolicy", "drop")
            labels = item.get("labels", [])
            public_comment = fires_labels_to_comment(labels, label_map)

            if policy in ALLOW_POLICIES:
                if not ignore_accept:
                    # Accept -> allowlist, remove from blocklist if present
                    allowlist.blocks[domain] = DomainBlock(
                        domain=domain,
                        severity="noop",
                        public_comment=public_comment,
                    )
                    if domain in blocklist.blocks:
                        del blocklist.blocks[domain]
            else:
                # Block recommendation
                severity = fires_policy_to_severity(policy)
                block = DomainBlock(
                    domain=domain,
                    severity=severity,
                    public_comment=public_comment,
                )
                max_sev = BlockSeverity(max_severity)
                if block.severity > max_sev:
                    block.severity = max_sev
                blocklist.blocks[domain] = block

                # If it was on the allowlist, remove it
                if domain in allowlist.blocks:
                    del allowlist.blocks[domain]

            # If this domain was previously retracted, undo that
            state.remove_retraction(dataset_url, domain)

        elif item_type == "Retraction":
            # Remove from both lists and record the retraction
            if domain in blocklist.blocks:
                log.info(f"FIRES retraction: removing {domain} from blocklist")
                del blocklist.blocks[domain]
            if domain in allowlist.blocks:
                log.info(f"FIRES retraction: removing {domain} from allowlist")
                del allowlist.blocks[domain]
            state.add_retraction(dataset_url, domain)

    return blocklist, allowlist


def fetch_fires_blocklist(
    server_url: str,
    dataset_id: str,
    state: FIRESState,
    max_severity: str = "suspend",
    max_pages: int = 50,
    ignore_accept: bool = False,
) -> tuple:
    """Fetch a blocklist and allowlist from a FIRES dataset.
    
    On first run (no cursor in state), fetches the full snapshot.
    On subsequent runs, polls the changes feed from the last cursor.
    
    Recommendations with 'accept' policy go to the allowlist.
    All other recommendations go to the blocklist.
    
    @param server_url: Base URL of the FIRES server
    @param dataset_id: UUID of the dataset to fetch
    @param state: FIRESState for cursor and retraction tracking
    @param max_severity: Maximum severity cap
    @param max_pages: Maximum number of changes pages to walk
    @returns: Tuple of (Blocklist, Blocklist) where the second is the allowlist
    """
    client = FIRESClient(server_url)
    dataset_url = f"{server_url}/datasets/{dataset_id}"

    # Build label name lookup
    label_map = build_label_map(client)

    # Check for existing cursor
    cursor = state.get_cursor(dataset_url)
    retractions = state.get_retractions(dataset_url)

    if cursor is None:
        # First run: fetch the full snapshot
        log.info(f"FIRES: fetching full snapshot for dataset {dataset_id}")
        snapshot = client.get_snapshot(dataset_id)

        blocklist, allowlist = snapshot_to_blocklist(
            snapshot, dataset_url, label_map, max_severity, retractions,
            ignore_accept
        )

        # Save the cursor from the snapshot for next time
        changes_url = snapshot.get("changes")
        if changes_url:
            state.set_cursor(dataset_url, changes_url)

        log.info(
            f"FIRES: snapshot loaded {len(blocklist)} blocks, "
            f"{len(allowlist)} allows from {dataset_url}"
        )

    else:
        # Incremental: start from snapshot, then apply changes
        log.info(f"FIRES: incremental update for dataset {dataset_id}")
        snapshot = client.get_snapshot(dataset_id)
        blocklist, allowlist = snapshot_to_blocklist(
            snapshot, dataset_url, label_map, max_severity, retractions,
            ignore_accept
        )

        # Walk the changes feed from our cursor
        all_changes = []
        page_url = cursor
        pages = 0

        while page_url and pages < max_pages:
            log.debug(f"FIRES: fetching changes page {pages + 1}")
            page = client.get_changes_from_url(page_url)
            items = page.get("orderedItems", [])

            if not items:
                break

            all_changes.extend(items)
            page_url = page.get("next")
            pages += 1

        if all_changes:
            log.info(
                f"FIRES: applying {len(all_changes)} changes from {pages} pages"
            )
            blocklist, allowlist = apply_changes(
                blocklist, allowlist, all_changes, label_map,
                state, dataset_url, max_severity, ignore_accept
            )

        # Update cursor to the latest position
        new_cursor = snapshot.get("changes")
        if new_cursor:
            state.set_cursor(dataset_url, new_cursor)

        log.info(
            f"FIRES: incremental update complete, {len(blocklist)} blocks, "
            f"{len(allowlist)} allows from {dataset_url}"
        )

    return blocklist, allowlist
