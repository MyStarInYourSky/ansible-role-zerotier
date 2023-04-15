from __future__ import absolute_import, division, print_function
__metaclass__ = type


DOCUMENTATION = '''
---
module: zerotier
version_added: "0.0.2"
short_description: Manages Zerotier
description:
    - Manages ZeroTier on a host
options:
    name:
        description:
            - Name of the current Node
        type: str
        required: true

    networks:
        description:
            - Networks as well as network configurations for the host
        type: dict
        required: true

author:
- MyStarInYourSky (@mystarinyoursky)
'''

EXAMPLES = '''
- name: Add host to ZeroTier Network
  zerotier:
    name: zz12345
    networks:
        123456:
            apikey: somekey
            nodedescription: someserver
            config:
                authorized: True
                hidden: False
                tags:
                    - [1001, 2001]
'''

RETURN = r'''
name:
  description: Zerotier Network ID
  returned: always
  type: str
  sample: zz12345
networks:
  description: Networks as well as network configurations for the host
  returned: always
  type: dict
  sample: True
'''

import grp
import os
import socket
import shutil
import json
import time
import os.path
import psutil

from ansible.module_utils._text import to_bytes
from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.urls import open_url

class ZeroTierNode(object):
    """
    Zerotier Node Class
    """

    def __init__(self, module):
        self.local_api_url = "http://localhost:9993"
        self.api_url = "https://api.zerotier.com"
        self.module = module
        self.nodename = module.params['name']
        self.networks = module.params['networks']

        # Set Defaults
        self.result = {}
        self.result['changed'] = False

        # Get Local ZT Token
        self.local_api_token = self.getZeroTierAuthToken()

        # Get ZT Status
        self.local_config = self.getZeroTierStatus()
        self.nodeid = self.local_config['address']

    def getZeroTierStatus(self):
        """
        Check if ZeroTier is installed, running, and accessible
        Make sure we can get and return the authtoken
        """
        api_url = self.local_api_url + '/status'
        api_auth = {'X-ZT1-Auth': self.local_api_token, 'Content-Type': 'application/json'}
        try:
            raw_resp = open_url(api_url, headers=api_auth, validate_certs=True, method='GET', timeout=10)
            if raw_resp.getcode() != 200:
                self.module.fail_json(changed=False, msg="Unable to authenticate with local ZeroTier service with local authtoken")
        except Exception as e:
            self.module.fail_json(changed=False, msg="Unable to reach local ZeroTier service (status)", reason=str(e))
        resp_json = json.loads(raw_resp.read())

        # Make sure node is online before we proceed
        run_count = 0
        max_run_wait = 10
        while run_count <= max_run_wait:
            if resp_json['online'] == True:
                run_count = max_run_wait
            run_count +=1
            time.sleep(2)

        return(resp_json)

    def getZeroTierAuthToken(self):
        """
        Get authtoken required for local zerotier-one API calls
        """
        try:
            with open('/var/lib/zerotier-one/authtoken.secret') as f:
                zerotier_token = f.readlines()
        except Exception as e:
            self.module.fail_json(changed=False, msg="Unable to read auth token of currently running ZeroTier Node", reason=str(e))
        return(zerotier_token[0])
    
    def getJoinedNetworks(self):
        """
        Get networks that are joined in the local ZT Node
        """
        api_url = self.local_api_url + '/network'
        api_auth = {'X-ZT1-Auth': self.local_api_token, 'Content-Type': 'application/json'}
        try:
            raw_resp = open_url(api_url, headers=api_auth, validate_certs=True, method='GET', timeout=10)
            if raw_resp.getcode() != 200:
                self.module.fail_json(changed=False, msg="Unable to authenticate with local ZeroTier service with local authtoken")
            else:
                resp_json = json.loads(raw_resp.read())
                networks = [networkconfig['nwid'] for networkconfig in resp_json]
                return(networks)
        except Exception as e:
            self.module.fail_json(changed=False, msg="Unable to reach local ZeroTier service (getjoinednetworks)", reason=str(e))
    
    def checkAPIKey(self, network):
        """
        Check if ZeroTier API Key works
        """
        api_url = self.api_url + '/api/network/' + network
        api_auth = {'Authorization': 'token ' + self.networks[network]['apikey'], 'Content-Type': 'application/json'}
        try:
            raw_resp = open_url(api_url, headers=api_auth, validate_certs=True, method='GET', timeout=10)
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
        api_url = self.local_api_url + '/network/' + network
        api_auth = {'X-ZT1-Auth': self.local_api_token, 'Content-Type': 'application/json'}
        try:
            raw_resp = open_url(api_url, headers=api_auth, validate_certs=True, method='POST', timeout=10)
            if raw_resp.getcode() != 200:
                self.module.fail_json(changed=False, msg="Unable to authenticate with local ZeroTier service with local authtoken")
            else:
                resp_json = json.loads(raw_resp.read())
                networks = [networkconfig['nwid'] for networkconfig in resp_json]
                return(networks)
        except Exception as e:
            self.module.fail_json(changed=False, msg="Unable to reach local ZeroTier service (joinnetwork)", reason=str(e))

    def leaveNetwork(self, network):
        """
        Remove node to network
        """
        api_url = self.local_api_url + '/network/' + network
        api_auth = {'X-ZT1-Auth': self.local_api_token, 'Content-Type': 'application/json'}
        try:
            raw_resp = open_url(api_url, headers=api_auth, validate_certs=True, method='DELETE', timeout=10)
            if raw_resp.getcode() != 200:
                self.module.fail_json(changed=False, msg="Unable to authenticate with local ZeroTier service with local authtoken")
            else:
                resp_json = json.loads(raw_resp.read())
                networks = [networkconfig['nwid'] for networkconfig in resp_json]
                return(networks)
        except Exception as e:
            self.module.fail_json(changed=False, msg="Unable to reach local ZeroTier service (leavenetwork)", reason=str(e))

    def setNodeConfig(self, config, network):
        """
        Sets node configuration
        """
        api_url = f"{self.api_url}/api/network/{network}/member/{self.nodeid}"
        api_auth = {'Authorization': 'token ' + self.networks[network]['apikey'], 'Content-Type': 'application/json'}
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
        api_url = f"{self.api_url}/api/network/{network}/member/{self.nodeid}"
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

    def buildNodeConfig(self, network):
        current_full_node_config = self.getNodeConfig(network)

        # Seperate the config key for clarity
        node_config = current_full_node_config['config']
        node_config.update(self.networks[network]['config'])

        # Set config key
        if node_config != current_full_node_config['config']:
            self.result['changed'] = True
            current_full_node_config['config'] = node_config

        if current_full_node_config['name'] != self.nodename:
            self.result['changed'] = True
            current_full_node_config['name'] = self.nodename

        if current_full_node_config['description'] != self.networks[network]['nodedescription:']:
            self.result['changed'] = True
            current_full_node_config['description'] = self.networks[network]['nodedescription:']

        # Send it away
        if self.result['changed'] == True:
            self.setNodeConfig(current_full_node_config, network)

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
            networks=dict(type='dict', required=False, default={}),
        ),
        supports_check_mode=True,
    )
    zerotier_node = ZeroTierNode(ansible_module)

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

    # Set Node Config
    for network in zerotier_node.getJoinedNetworks():
        zerotier_node.buildNodeConfig(network)

    # Emit status
    if zerotier_node.result['changed']:
        ansible_module.exit_json(changed=True, msg="Zerotier config updated")
    else:
        ansible_module.exit_json(changed=False, msg="Zerotier config unchanged")


# import module snippets
if __name__ == '__main__':
    main()
