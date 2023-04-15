# Ansible role for ZeroTier

This ansible role provides full control of node settings through the ZeroTier API as well as local settings.

## Features

- Joining/Leaving of nodes from networks using API calls to the local ZT node API
- Configuration of node settings in a network the node has joined
- Local configuration of node settings (localconfig)

## Tested Operating Systems

- Ubuntu 18.04
- Ubuntu 20.04
- Ubuntu 22.04

## Parameters

### `zerotier_version`

The zerotier version that will be installed

### `zerotier_networks`

Configuration of zerotier networks that the node will join.

It uses the following structure

```yaml
{{zerotier network id}}:
    apikey: {{zerotier_api_key}}
    nodedescription: zerotier node description
    config: {{zerotier_config}}
```

### `zerotier_network_id`

This is the ID of the zerotier network the node is to join

### `zerotier_api_key`

This is the API key used for your zerotier account.
Can be retrieved from ZeroTier Central -> Account -> New Token

### `zerotier_config`

This dict sets any config under the `config` secton of a network member. See https://docs.zerotier.com/central/v1/#operation/updateNetworkMember for more details. Very important for authorizing (i.e. `authorized: True`) nodes automatically.

## Example Deployment

```yaml
zerotier_version: 1.10.6
zerotier_networks:
  12345:
    apikey: myapikey
    nodedescription: myserver
    config:
      authorized: True
      tags:
        - [1001, 2001]
```
