# Ansible role for ZeroTier

Manages:
- Installation of ZeroTier One
- Version Pinning
- Joining ZeroTier Node to a ZeroTier Network
- Setting the [config](https://docs.zerotier.com/central/v1#operation/updateNetworkMember) of a ZeroTier Node in a ZeroTier Network


## Config

### `zerotier_version`
Configures the ZeroTier One version to install


Example
```
zerotier_version: 1.4.6
```

## `zerotier_networks`
Configures the ZeroTier One networks on the host.
You can check the allowed config options in the [ZeroTier API Docs](https://docs.zerotier.com/central/v1#operation/updateNetworkMember)


Example
```
zerotier_networks:
  <network id 1>:
    apikey: <zerotier api key>
    nodedescription: Network Router
    hidden: False
    config:
      authorized: True
  <network id 2>:
    apikey: <zerotier api key>
    nodedescription: Network Router
    hidden: False
    config:
      authorized: False
      tags:
        - [1001, 1001]
```

## `zerotier_localconfig`
Configures the local ZeroTier One config at /var/lib/zerotier-one/local.conf.
See more info at the [ZeroTier Local Configuration Options](https://docs.zerotier.com/zerotier/zerotier.conf/#42localconfigurationoptionsaname4_2a)

Example
```
zerotier_localconfig:
  settings:
    primaryPort: 9993
    portmappingEnabled: false
    allowSecondaryPort: false
    allowTcpFallbackRelay: false
```
