from __future__ import absolute_import, division, print_function
__metaclass__ = type


DOCUMENTATION = '''
---
module: zerotier
version_added: "0.0.1"
short_description: Manages Zerotier
description:
    - Manages ZeroTier on a host
options:
    name:
        description:
            - ID of the ZeroTier network to manage
        type: str
        required: true
    nodename:
        description:
            - Sets the alias of the remote host in the ZeroTier network
        type: str
        required: false
    nodedescription:
        description:
            - Sets the description of the remote host in the ZeroTier network
        type: str
        required: false
    config:
        description:
            - Sets the ZeroTier node config
        type: dict
        required: false
    hidden:
        description:
            - Whether the remote host should be hidden in the ZeroTier network
        type: boolean
        choices: [ yes, no ]
        default: yes
    apikey:
        description:
            - The API key used for ZeroTier API calls
        type: str
        required: true
    joined:
        description:
            - Whether the remote host has joined the ZeroTier network
        type: boolean
        choices: [ yes, no ]
        default: yes

author:
- ILoveYaToo (@iloveyatoo)
'''

EXAMPLES = '''
- name: Add host to ZeroTier Network
  zerotier:
    name: zz12345
    auth: yes
    apikey: mykey12345
'''

RETURN = r'''
name:
  description: Zerotier Network ID
  returned: always
  type: str
  sample: zz12345
auth:
  description: Whether the remote host is authenticated in the ZeroTier network
  returned: always
  type: bool
  sample: True
hidden:
  description: Whether the remote host is hidden in the ZeroTier network
  returned: always
  type: bool
  sample: False
nodename:
  description: Alias of the remote host in the ZeroTier network
  returned: always
  type: str
  sample: MyHost
joined:
  description: Whether the remote host has joined the ZeroTier network
  returned: always
  type: bool
  sample: False  
'''

import grp
import os
import socket
import shutil
import json
import time

from ansible.module_utils._text import to_bytes
from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.urls import open_url

class ZeroTierNode(object):
    """
    Zerotier Node Class
    """

    def __init__(self, module):
        self.api_url = "https://api.zerotier.com"
        self.module = module
        self.nodename = module.params['name']
        self.networks = module.params['networks']
        self.localconfig = module.params['localconfig']

        # Set Defaults
        self.result = {}
        self.result['changed'] = False

    def getZeroTierInstallStatus(self):
        """
        Check if ZeroTier is installed
        """
        if shutil.which("zerotier-cli"):
            return True
        else:
            return False
    
    def getZeroTierClientAccess(self):
        """
        Check if the zerotier-cli client can reach the zerotier-one instance running on node
        """
        command_result =  self.module.run_command(['zerotier-cli', 'listnetworks', 'info'])
        if command_result[0] != 0:
            return False
        else:
            return True
        
    def getNodeID(self):
        """
        Gets local ZeroTier Network ID
        """
        with open('/var/lib/zerotier-one/identity.public', 'r') as fh:
            node = fh.readline().split(":")[0]
        return node
    
    def getJoinedNetworks(self):
        """
        Get networks that are joined in the local ZT Node
        """
        result =  self.module.run_command(['zerotier-cli', 'listnetworks', '-j', '|', 'jq', '-r', '[.[].nwid]'])
        json_result=json.loads(result[1])
        return json_result
    
    def checkAPIKey(self, network):
            """
            Check if ZeroTier API Key works
            """
            api_url = self.api_url + '/api/network/' + network
            api_auth = {'Authorization': 'token ' + self.apikey, 'Content-Type': 'application/json'}
            try:
                raw_resp = open_url(api_url, headers=api_auth, validate_certs=True)
                if raw_resp.getcode() == 403:
                    self.module.fail_json(changed=False, msg="Unable to authenticate with ZeroTier API!")
                elif raw_resp.getcode() == 404:
                    self.module.fail_json(changed=False, msg="ZeroTier network does not exist")
                elif raw_resp.getcode() == 200:
                    return True
            except Exception as e:
                self.module.fail_json(changed=False, msg="Unable to reach ZeroTier API", reason=str(e))

    def joinNetwork(self, network):
        """
        Join node to network
        """
        result =  self.module.run_command(['zerotier-cli', 'join', network])
        self.result['changed'] = True
        return result

    def leaveNetwork(self, network):
        """
        Removes node from network
        """
        result = self.module.run_command(['zerotier-cli', 'leave', network])
        self.result['changed'] = True
        return result

    def setNodeConfig(self, config):
        """
        Sets node configuration
        """
        api_url = f"{self.api_url}/api/network/{self.network}/member/{self.node}"
        api_auth = {'Authorization': 'token ' + self.apikey, 'Content-Type': 'application/json'}
        config_json = json.dumps(config)
        try:
            raw_resp = open_url(api_url, headers=api_auth, method="POST", data=config_json)
            if raw_resp.getcode() == 403:
                self.module.fail_json(changed=False, msg="Unable to authenticate with ZeroTier API!")
            elif raw_resp.getcode() == 404:
                self.module.fail_json(changed=False, msg="ZeroTier network or node does not exist")
            elif raw_resp.getcode() == 200:
                return True
        except Exception as e:
            self.module.fail_json(changed=False, msg="Unable to set config of ZeroTier node " + self.node, reason=str(e))

    def getNodeConfig(self, network):
        """
        Gets node configuration
        """
        api_url = self.api_url + '/api/network/' + network + '/member/' + self.nodename
        api_auth = {'Authorization': 'token ' + self.networks[network]['apikey'], 'Content-Type': 'application/json'}
        try:
            raw_resp = open_url(api_url, headers=api_auth, method="GET")
            if raw_resp.getcode() == 403:
                self.module.fail_json(changed=False, msg="Unable to authenticate with ZeroTier API!")
            elif raw_resp.getcode() == 404:
                self.module.fail_json(changed=False, msg="ZeroTier network does not exist")
            elif raw_resp.getcode() == 200:
                resp = json.loads(raw_resp.read())
                return resp
        except Exception as e:
            self.module.fail_json(changed=False, msg="Unable to get config of ZeroTier node " + self.node, reason=str(e))

    def buildNodeConfig(self, network, hidden, nodename, nodedescription, config):
        current_full_node_config = self.getNodeConfig(network)

        # Seperate the config key for clarity
        node_config = current_full_node_config['config']
        node_config.update(config)

        # Set config key
        if node_config != current_full_node_config['config']:
            self.result['changed'] = True
            current_full_node_config['config'] = node_config

        # Set some additional variables
        if current_full_node_config['hidden'] != hidden:
            self.result['changed'] = True
            current_full_node_config['hidden'] = hidden
        if current_full_node_config['name'] != nodename:
            self.result['changed'] = True
            current_full_node_config['name'] = nodename
        if current_full_node_config['description'] != nodedescription:
            self.result['changed'] = True
            current_full_node_config['description'] = nodedescription

        # Send it away
        self.setNodeConfig(current_full_node_config)

    def compareTargetJoinedNetworks(self):
        remove_networks = list(set(self.getJoinedNetworks()) - set(self.networks.keys()))
        add_networks = list(set(self.networks.keys()) - set(self.getJoinedNetworks()))
        return (add_networks, remove_networks)
        

def main():
    ssh_defaults = dict(
        bits=0,
        type='rsa',
        passphrase=None,
        comment='ansible-generated on %s' % socket.gethostname()
    )

    # Init Node Config
    ansible_module = AnsibleModule(
        argument_spec=dict(
            name=dict(type='str', required=True),
            networks=dict(type='str', required=False, default={}),
            localconfig=dict(type='dict', required=False, default={})
        ),
        supports_check_mode=True,
    )
    zerotier_node = ZeroTierNode(ansible_module)

    # Checks to make sure this can run properly

    ## Make sure we can run zerotier-cli
    if zerotier_node.getZeroTierInstallStatus == False:
        ansible_module.fail_json(changed=False, msg="ZeroTier installation cannot be located in $PATH. Check your installation.")

    ## Make sure the zerotier-cli client can connect to the node
    if zerotier_node.getZeroTierClientAccess == False:
       ansible_module.fail_json(changed=False, msg="ZeroTier client cannot reach node config, check if ZeroTier is running and the user running the client can access credentials.")

    # Compare list of target networks and currently joined networks
    zerotier_add_networks, zerotier_remove_networks = zerotier_node.compareTargetJoinedNetworks()

    # Join Networks
    for network in zerotier_add_networks:
        zerotier_node.checkAPIKey(network)
        zerotier_node.joinNetwork(network)

    # Leave Networks
    for network in zerotier_remove_networks:
        zerotier_node.checkAPIKey(network)
        zerotier_node.leaveNetwork(network)

    # Sleep to make sure API has received data
    time.sleep(10)


    if zerotier.joined:
        # Check if API Key is valid for the specified network
        zerotier.checkAPIKey()

        # Apply Config
        zerotier.buildNodeConfig()

        if zerotier.result['changed']:
            module.exit_json(changed=True, msg="Zerotier config updated")
        else:
            module.exit_json(changed=False, msg="Zerotier config unchanged")


# import module snippets
if __name__ == '__main__':
    main()
