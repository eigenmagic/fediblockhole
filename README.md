# FediBlockHole

A tool for keeping a Mastodon instance blocklist synchronised with remote lists.

The broad design goal for FediBlockHole is to support pulling in a list of
blocklists from a set of trusted sources, merge them into a combined blocklist,
and then push that merged list to a set of managed instances.

Mastodon admins can choose who they think maintain quality lists and subscribe
to them, helping to distribute the load for maintaining blocklists among a
community of people. Control ultimately rests with the admins themselves so they
can outsource as much, or as little, of the effort to others as they deem
appropriate.

Inspired by the way PiHole works for maintaining a set of blocklists of adtech
domains. Builds on the work of
[@CaribenxMarciaX@scholar.social](https://scholar.social/@CaribenxMarciaX) and
[@gingerrroot@kitty.town](https://kitty.town/@gingerrroot) who started the
#Fediblock hashtag and did a lot of advocacy around it, often at great personal
cost.

## Features

### Blocklist Sources

 - Read domain block lists from other instances via the Mastodon API.
 - Supports both public lists (no auth required) and 'admin' lists requiring
   authentication to an instance.
 - Read domain block lists from arbitrary URLs, including local files.
 - Supports CSV and JSON format blocklists
 - Supports RapidBlock CSV and JSON format blocklists
 - Consume moderation recommendations from [FIRES](https://github.com/fedimod/fires) datasets, with support for retractions, labels, and incremental polling

### Blocklist Export/Push

 - Push a merged blocklist to a set of Mastodon instances.
 - Export per-source, unmerged block lists to local files, in CSV format.
 - Export merged blocklists to local files, in CSV format.
 - Read block lists from multiple remote instances
 - Read block lists from multiple URLs, including local files
 - Write a unified block list to a local CSV file
 - Push unified blocklist updates to multiple remote instances
 - Control import and export fields

### Flexible Configuration

 - Provides (hopefully) sensible defaults to minimise first-time setup.
 - Global and fine-grained configuration options available for those complex situations that crop up sometimes.
 - Allowlists to override blocks in blocklists to ensure you never block instances you want to keep.
 - Blocklist thresholds if you want to only block when an instance shows up in multiple blocklists.

## Installing

Installable using `pip`.

```
python3 -m pip install fediblockhole
```

Install from source by cloning the repo, `cd fediblockhole` and run:

```
python3 -m pip install .
```

Installation adds a commandline tool: `fediblock-sync`

Instance admins who want to use this tool for their instance will need to add an
Application at `https://<instance-domain>/settings/applications/` so they can
authorize the tool to create and update domain blocks with an OAuth token.

More on authorization by token below.

### Reading remote instance blocklists

If a remote instance makes its domain blocks public, you don't need
a token to read them.

If a remote instance only shows its domain blocks to local accounts
you'll need to have a token with `read:blocks` authorization set up.
If you have an account on that instance, you can get a token by setting up a new
Application at `https://<instance-domain>/settings/applications/`.

To read admin blocks from a remote instance, you'll need to ask the instance
admin to add a new Application at
`https://<instance-domain>/settings/applications/` and then tell you the access
token.

The application needs the `admin:read:domain_blocks` OAuth scope. You can allow
full `admin:read` access, but be aware that this authorizes someone to read all
the data in the instance. That's asking a lot of a remote instance admin who
just wants to share domain_blocks with you.

The `admin:read:domain_blocks` scope is available as of Mastodon v4.1.0, but for
earlier versions admins will need to use the manual method described below.

You can update the scope for your application in the database directly like
this:

```
UPDATE oauth_applications as app
  SET scopes = 'admin:read:domain_blocks'
  FROM oauth_access_tokens as tok
  WHERE app.id = tok.application_id
  AND app.name = '<the_app_name>'
;
```

When that's done, regenerate the token (so it has the new scopes) in the
application screen in the instance GUI. FediBlockHole should then able to use
the app token to read domain blocks via the API, but nothing else.

Alternately, you could ask the remote instance admin to set up FediBlockHole and
use it to dump out a CSV blocklist from their instance and then put it somewhere
trusted parties can read it. Then you can define the blocklist as a URL source,
as explained below.

### Writing instance blocklists

To write domain blocks into an instance requires both the `admin:read` and
`admin:write:domain_blocks` OAuth scopes.

The tool needs `admin:read:domain_blocks` scope to read the current list of
domain blocks so we update ones that already exist, rather than trying to add
all new ones and clutter up the instance.

`admin:read` access is needed to check if the instance has any accounts that
follow accounts on a domain that is about to get `suspend`ed and automatically
drop the block severity to `silence` level so people have time to migrate
accounts before a full defederation takes effect. Unfortunately, the statistics
measure used to learn this information requires `admin:read` scope.

You can add `admin:read` scope in the application admin screen. Please be aware
that this grants full read access to all information in the instance to the
application token, so make sure you keep it a secret. At least remove
world-readable permission to any config file you put it in, e.g.:

```
chmod o-r <configfile>
```

You can also grant full `admin:write` scope to the application, but if you'd
prefer to keep things more tightly secured, limit the scope to
`admin:read:domain_blocks`.

Again, this scope is only available in the application config screen as of
Mastodon v4.1.0. If your instance is on an earlier version, you'll need to use
SQL to set the scopes in the database and then regenerate the token:

```
UPDATE oauth_applications as app
  SET scopes = 'admin:read admin:write:domain_blocks'
  FROM oauth_access_tokens as tok
  WHERE app.id = tok.application_id
  AND app.name = '<the_app_name>'
;
```

When that's done, FediBlockHole should be able to use its token to authorise
adding or updating domain blocks via the API.

## Using the tool

Run the tool like this:

```
fediblock-sync -c <configfile_path>
```

If you put the config file in `/etc/default/fediblockhole.conf.toml` you don't
need to pass in the config file path.

For a list of possible configuration options, check the `--help`.

You can also read the heavily commented sample configuration file in the repo at
[etc/sample.fediblockhole.conf.toml](https://github.com/eigenmagic/fediblockhole/blob/main/etc/sample.fediblockhole.conf.toml).

## Configuring

Once you have your applications and tokens and scopes set up, create a
configuration file for FediBlockHole to use. You can put it anywhere and use the
`-c <configfile>` commandline parameter to tell FediBlockHole where it is.

Or you can use the default location of `/etc/default/fediblockhole.conf.toml`.

As the filename suggests, FediBlockHole uses TOML syntax.

There are 5 key sections:
 
 1. `blocklist_url_sources`: A list of URLs to read blocklists from
 1. `blocklist_instance_sources`: A list of Mastodon instances to read blocklists from via API
 1. `blocklist_fires_sources`: A list of FIRES servers/datasets to read moderation data from
 1. `blocklist_instance_destinations`: A list of Mastodon instances to write blocklists to via API
 1. `allowlist_url_sources`: A list of URLs to read allowlists from

More detail on configuring the tool is provided below.

### URL sources

The URL sources is a list of URLs to fetch blocklists from.

Supported formats are currently:

 - Comma-Separated Values (CSV)
 - JSON
 - Mastodon v4.1 flavoured CSV
 - RapidBlock CSV
 - RapidBlock JSON

Blocklists must provide a `domain` field, and should provide a `severity` field.

`domain` is the domain name of the instance to be blocked/limited.

`severity` is the severity level of the block/limit. Supported values are: `noop`, `silence`, and `suspend`.

Optional fields that the tool understands are `public_comment`, `private_comment`, `reject_media`, `reject_reports`, and `obfuscate`.

#### CSV format

A CSV format blocklist must contain a header row with at least a `domain` and `severity` field.

Optional fields, as listed about, may also be included.

#### Mastodon v4.1 CSV format

As of v4.1.0, Mastodon can export domain blocks as a CSV file. However, in their
infinite wisdom, the Mastodon devs decided that field names should begin with a
`#` character in the header, unlike the field names in the JSON output via the
API… or in pretty much any other CSV file anywhere else.

Setting the format to `mastodon_csv` will strip off the `#` character when
parsing and FediBlockHole can then use Mastodon v4.1 CSV blocklists like any
other CSV formatted blocklist.

#### JSON format

JSON is also supported. It uses the same format as the JSON returned from the Mastodon API.

This is a list of dictionaries, with at minimum a `domain` field, and preferably
a `severity` field. The other optional fields are, well, optional.

#### RapidBlock CSV format

The RapidBlock CSV format has no header and a single field, so it's not
_strictly_ a CSV file as there are no commas separating values. It is basically
just a list of domains to block, separated by '\r\n'.

When using this format, the tool assumes the `severity` level is `suspend`.

#### RapidBlock JSON format

The RapidBlock JSON format provides more detailed information about domain
blocks, but is still somewhat limited.

It has a single `isBlocked` flag indicating if a domain should be blocked or
not. There is no support for the 'silence' block level.

There is no support for 'reject_media' or 'reject_reports' or 'obfuscate'.

All comments are public, by virtue of the public nature of RapidBlock.

### Instance sources

The tool can also read domain_blocks from instances directly.

The configuration is a list of dictionaries of the form:
```
{ domain = '<domain_name>', token = '<BearerToken>', admin = false }
```

The `domain` is the fully-qualified domain name of the API host for an instance
you want to read domain blocks from. 

The `token` is an optional OAuth token for the application that's configured in
the instance to allow you to read domain blocks, as discussed above.

The `token` can also be specified using environment variables. This provides
improved security compared to storing the OAuth token in a configuration file,
but it will require the environment variable to be set so that FediBlockHole can
access it. See below in [Instance destinations](#instance-destinations) for more
detail on how to use environment variables to provide authentication tokens.

`admin` is an optional field that tells the tool to use the more detailed admin
API endpoint for domain_blocks, rather than the more public API endpoint that
doesn't provide as much detail. You will need a `token` that's been configured to
permit access to the admin domain_blocks scope, as detailed above.

### Instance destinations

The tool supports pushing a unified blocklist to multiple instances.

Configure the list of instances you want to push your blocklist to in the
`blocklist_instance_destinations` list. Each entry is of the form:

```
{ domain = '<domain_name>', import_fields = ['public_comment'], max_severity = 'suspend', max_followed_severity = 'suspend' }
```

The field `domain` is required. It is the fully-qualified domain name of the
instance you want to push to. 

A BearerToken is also required, for authenticating with the instance. It can be provided in two ways:

1. A token can be provided directly in the entry as a `token` field, like this:
    ```
    { domain = '<domain_name>', token = '<BearerToken>', import_fields = ['public_comment'], max_severity = 'suspend', max_followed_severity = 'suspend' }
    ```
    This was the only mechanism available up to version 0.4.5 of Fediblockhole.

1. A token can be provided from the environment.

    If a token is not directly provided with the `token` field, Fediblockhole will
    look for an environment variable that contains the token.

    By default, the name of the environment variable will be the domain name
    converted to upper case and with dot/period characters converted to
    underscores, and the suffix `_TOKEN`. For example, the token variable for the
    domain `eigenmagic.net` would be `EIGENMAGIC_NET_TOKEN`.

    You can also specify the environment variable to look for, using the
    `token_env_var` field, like this:
    ```
    { domain = '<domain_name>', token_env_var = 'MY_CUSTOM_DOMAIN_TOKEN', import_fields = ['public_comment'], max_severity = 'suspend', max_followed_severity = 'suspend' }
    ```

    Fediblockhole will then look for a token in the `MY_CUSTOM_DOMAIN_TOKEN` environment variable.

    If a specific `token_env_var` is provided, the default variable name will
    not be used. If both the `token` and `token_env_var` fields are provided,
    the token provided in the `token` field will be used, and a warning will be
    issued to notify you that you might have misconfigured things.


The BearerToken is
an application token with both `admin:read:domain_blocks` and
`admin:write:domain_blocks` authorization.

The fields `max_followed_severity` and `import_fields` are optional.

The optional `import_fields` setting allows you to restrict which fields are
imported from each instance. If you want to import the `reject_reports` settings
from one instance, but no others, you can use the `import_fields` setting to do
it. **Note:** The `domain` and `severity` fields are always imported.

The optional `max_severity` setting limits the maximum severity you will allow a
remote blocklist to set. This helps you import a list from a remote instance but
only at the `silence` level, even if that remote instance has a block at
`suspend` level. If not set, defaults to `suspend`.

The optional `max_followed_severity` setting sets a per-instance limit on the
severity of a domain_block if there are accounts on the instance that follow
accounts on the domain to be blocked. If `max_followed_severity` isn't set, it
defaults to `silence`.

This setting exists to give people time to move off an instance that is about to
be defederated and bring their followers from your instance with them. Without
it, if a new `suspend` block appears in any of the blocklists you subscribe to (or
a block level increases from `silence` to `suspend`) and you're using the default
`max` mergeplan, the tool would immediately suspend the instance, cutting
everyone on the blocked instance off from their existing followers on your
instance, even if they move to a new instance. If you actually want that
outcome, you can set `max_followed_severity = 'suspend'` and use the `max`
mergeplan.

Once the follow count drops to 0 on your instance, the tool will automatically
use the highest severity it finds again (if you're using the `max` mergeplan).

### Allowlists

Sometimes you might want to completely ignore the blocklist definitions for
certain domains. That's what allowlists are for.

Allowlists remove any domain in the list from the merged list of blocks before
the merged list is saved out to a file or pushed to any instance.

Allowlists can be in any format supported by `blocklist_urls_sources` but ignore
all fields that aren't `domain`.

You can also allow domains on the commandline by using the `-A` or `--allow`
flag and providing the domain name to allow. You can use the flag multiple
times to allow multiple domains.

It is probably wise to include your own instance domain in an allowlist so you
don't accidentally defederate from yourself.

## FIRES Integration

FediBlockHole can consume moderation data from [FIRES](https://github.com/fedimod/fires)
(Fediverse Intelligence Replication Endpoint Server) datasets. FIRES is an open
protocol for sharing moderation recommendations across the Fediverse, providing
structured data with labels, policies, change tracking, and retractions.

### How it works

FIRES datasets publish moderation recommendations as structured data. Each
recommendation includes a domain, a policy (`drop`, `reject`, `filter`, or
`accept`), and optional labels describing why the recommendation exists.

FediBlockHole maps these to Mastodon block semantics:

 - **drop** and **reject** become `suspend` blocks
 - **filter** becomes a `silence` block
 - **accept** feeds into the allowlist pipeline (see below)
 - **Retractions** remove a domain from that source's contribution

Only recommendations with `entityKind` of `domain` are processed. FIRES also
supports `actor`-level recommendations, but Mastodon's domain block API operates
at the domain level, so actor recommendations are silently skipped.

FIRES changes come in four types, each handled differently:

 - **Recommendation**: Creates or updates a block. This is the actionable one.
 - **Advisory**: Informational only — no block is created. If a domain is
   downgraded from Recommendation to Advisory, it effectively falls out of
   the blocklist (a soft retraction without fully removing it from the dataset).
 - **Retraction**: The source explicitly says "stop blocking this." The domain
   is removed from the source's contribution and, if `retractions = true`,
   can be deleted from the server.
 - **Tombstone**: Historical record cleanup. Silently skipped.

Each FIRES dataset counts as one source for threshold calculations. If you
subscribe to 3 FIRES datasets and 2 CSV blocklists, a domain needs to appear
in `threshold` of those 5 sources to be included in the merged blocklist.

### Configuration

Add FIRES sources to your config file using the `blocklist_fires_sources` list.
Each entry must have a `dataset` key pointing to the full dataset URL. The dataset
URL is the canonical identifier per the FIRES spec.

```toml
blocklist_fires_sources = [
  { dataset = 'https://fires.example/datasets/019d3565-f022-abbc-c43d649f294b' },
  { dataset = 'https://fires.example/datasets/019d3565-aabb-ccdd-eeff-112233445566', max_severity = 'silence' },
  { dataset = 'https://trusted-fires.example/datasets/uuid', retractions = true },
]
```

The dataset URL is opaque — FediBlockHole fetches it with an `Accept: application/ld+json`
header and the dataset metadata tells it where the snapshot and changes endpoints are.
No path construction, no assumptions about URL structure.

Label names are resolved by fetching each label URL found in the snapshot data.
FIRES snapshots include full label URLs (e.g., `http://fires.example/labels/uuid`)
which are individually fetchable resources. No separate labels collection endpoint
is needed.

FIRES datasets are public, so no authentication is required to read them.

Optional per-source settings:

 - `max_severity`: Cap the maximum severity applied (e.g., `'silence'`). Defaults to `'suspend'`.
 - `ignore_accept`: When `true`, `accept` policies won't be added to the allowlist. However, `accept` still removes any block that this dataset previously added — it acts as an implicit retraction. Defaults to `false`.
 - `retractions`: When `true`, honor retractions from this source by removing blocks from your instance. See the Retractions section below. Defaults to `false`.

### State tracking and retractions

FediBlockHole maintains a JSON state file to track its position in each
dataset's changes feed. On the first run, it fetches the full snapshot. On
subsequent runs, it polls only for new changes since the last run.

When a FIRES dataset publishes a **retraction** (meaning "we no longer recommend
blocking this domain"), FediBlockHole removes that domain from the source's
contribution to the merge. If other sources still recommend blocking it, the
block remains. Retractions only affect the source that issued them.

The state file defaults to `~/.fediblockhole/fires_state.json`. You can override
this with the `fires_state_file` config option or the `--fires-state-file`
commandline flag.

### The `accept` policy

The FIRES protocol includes an `accept` policy for recommending that a domain
*should* be federated with. FediBlockHole handles `accept` the same way it
handles its existing allowlists: domains with an `accept` recommendation are
removed from the merged blocklist before it is pushed to instances.

This means an `accept` from a FIRES dataset acts as an override, the same as
adding a domain to a CSV allowlist. It does not call any instance API to
explicitly allow the domain — it simply prevents it from being blocked.

If you don't want FIRES `accept` policies to influence your blocklist at all,
set `ignore_accept = true` on the source:

```toml
blocklist_fires_sources = [
  { dataset = 'https://fires.example/datasets/uuid', ignore_accept = true },
]
```

With `ignore_accept` enabled, `accept` recommendations are silently skipped.
Block recommendations (`drop`, `reject`, `filter`) and retractions still work
normally.

### Retractions: removing data that is no longer recommended or advised

Historically, FediBlockHole has been additive — it adds and updates blocks but
never removes them. This is safe but means blocks stay on your instance forever,
even if every source stops recommending them.

FIRES changes this by providing the state that blocklists never had. When a
FIRES dataset retracts a recommendation, FediBlockHole can now act on it.

There are two retraction mechanisms, and they can be used together:

#### Source-level retractions (`retractions = true`)

This is the FIRES-native approach. When a trusted FIRES source retracts a
domain (either via an explicit `Retraction` or an `accept` recommendation),
the block is removed from your instance — but only if that block was originally
added by the same dataset. A retraction from dataset A won't remove a block
that dataset B added.

Blocks created from FIRES datasets are stamped with `FIRES:{dataset_url}` in
the `private_comment` field. Retraction removal checks this stamp to confirm
ownership before acting. If no other source in your merged list still recommends
blocking the domain, the block is removed.

```toml
blocklist_fires_sources = [
  { dataset = 'https://fires.trusted.example/datasets/uuid-1', retractions = true },
  { dataset = 'https://other-fires.example/datasets/uuid-2', retractions = true },
]
```

The safeguard is the merge: if *any* other source (FIRES, CSV, instance) still
recommends blocking that domain, the retraction is countered and the block stays.

#### General retractions (`apply_retractions = true`)

This is a broader mechanism that works with any source type, not just FIRES.
When enabled, blocks that exist on your instance but are no longer in *any*
source are removed — but only if they were originally added by FediBlockHole.

This requires `override_private_comment` to be set, so FediBlockHole can
identify its own blocks by matching the stamp in `private_comment`. Blocks added
manually by the admin (with a different or no private comment) are never touched.

```toml
override_private_comment = 'Added by FediBlockHole'
apply_retractions = true
```

This can also be set per-destination instance:

```toml
blocklist_instance_destinations = [
  { domain = 'myinstance.social', token = '...', apply_retractions = true },
]
```

#### A note on general retractions and reliability

The general `apply_retractions` mechanism compares the merged list against what's
on your server. If a source goes offline or a URL is temporarily unreachable,
domains from that source will be absent from the merge, and `apply_retractions`
could remove them from your server even though nothing was actually retracted.

For this reason, it's often best to write the merged blocklist to a file first
(`blocklist_savefile`), review it, and then apply it in a separate run. Reading
from the filesystem is reliable — remote sources are not.

FIRES source-level retractions (`retractions = true`) don't have this problem.
They only act on domains that a FIRES dataset *explicitly* retracted via a
`Retraction` change entry. A dataset being unreachable doesn't generate
retractions — it just means no new changes are processed that run.

#### How they differ

| | Source retractions | General retractions |
|---|---|---|
| Trigger | FIRES dataset retracts or accepts a domain | Domain falls out of all sources |
| Scope | Only removes blocks added by the retracting dataset | Only removes blocks FediBlockHole added |
| Requires `override_private_comment` | No | Yes |
| Requires `retractions = true` on source | Yes | No (global or per-destination) |
| Works with CSV/instance sources | No (FIRES only) | Yes (any source) |

Both mechanisms respect the merge: if any source still recommends blocking a
domain, the block stays. Use `--dryrun` to preview what would be removed
without actually deleting anything.

### Commandline flags

 - `--no-fetch-fires`: Skip fetching from FIRES datasets even if configured.
 - `--fires-state-file <path>`: Override the state file location.
 - `--apply-retractions`: Enable retraction-based block removal (see above).

## More advanced configuration

For a list of possible configuration options, check the `--help` and read the
sample configuration file in `etc/sample.fediblockhole.conf.toml`.

### save_intermediate

This option tells the tool to save the unmerged blocklists it fetches from
remote instances and URLs into separate files. This is handy for debugging, or
just to have a non-unified set of blocklist files.

Works with the `savedir` setting to control where to save the files.

These are parsed blocklists, not the raw data, and so will be affected by `import_fields`.

The filename is based on the URL or domain used so you can tell where each list came from.

### savedir

Sets where to save intermediate blocklist files. Defaults to `/tmp`.

### blocklist_auditfile

If provided, will save an audit file of counts and percentages by domain. Useful for debugging 
thresholds. Defaults to None.

### no_push_instance

Defaults to False.

When set, the tool won't actually try to push the unified blocklist to any
configured instances.

If you want to see what the tool would try to do, but not actually apply any
updates, use `--dryrun`.

### no_fetch_url

Skip the fetching of blocklists from any URLs that are configured.

### no_fetch_instance

Skip the fetching of blocklists from any remote instances that are configured.

### override_private_comment

Defaults to None.

Stamp all *new* blocks pushed to a remote server with this comment or code. 
Helps to identify blocks you've created on a server via Fediblockhole versus ones that
already existed.

### mergeplan

If two (or more) blocklists define blocks for the same domain, but they're
different, `mergeplan` tells the tool how to resolve the conflict.

`max` is the default. It uses the _highest_ severity block it finds as the one
that should be used in the unified blocklist.

`min` does the opposite. It uses the _lowest_ severity block it finds as the one
to use in the unified blocklist.

A full discussion of severities is beyond the scope of this README, but here is
a quick overview of how it works for this tool.

The severities are:

 - **noop**, level 0: This is essentially an 'unblock' but you can include a
   comment.
 - **silence**, level 1: A silence adds friction to federation with an instance.
 - **suspend**, level 2: A full defederation with the instance.

With `mergeplan` set to `max`, _silence_ would take precedence over _noop_, and
_suspend_ would take precedence over both.

With `mergeplan` set to `min`, _silence_ would take precedence over _suspend_,
and _noop_ would take precedence over both.

You would want to use `max` to ensure that you always block with whichever your
harshest fellow admin thinks should happen.

You would want to use `min` to ensure that your blocks do what your most lenient
fellow admin thinks should happen.

### import_fields

`import_fields` controls which fields will be imported from remote
instances and URL blocklists, and which fields are pushed to instances from the
unified blocklist.

The fields `domain` and `severity` are always included, so only define extra
fields, if you want them.

You can't export fields you haven't imported, so `export_fields` should be a
subset of `import_fields`, but you can run the tool multiple times. You could,
for example, include lots of fields for an initial import to build up a
comprehensive list for export, combined with the `--no-push-instances` option so
you don't actually apply the full list to anywhere.

Then you could use a different set of options when importing so you have all the
detail in a file, but only push `public_comment` to instances.

### export_fields

`export_fields` controls which fields will get saved to the unified blocklist
file, if you export one.

The fields `domain` and `severity` are always included, so only define extra
fields, if you want them.