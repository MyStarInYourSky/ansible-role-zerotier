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
    Zerotier manipulation class
    """

    def __init__(self, module):
        self.api_url = "https://my.zerotier.com"
        self.module = module
        self.network = module.params['name']
        self.hidden = module.params['hidden']
        self.nodename = module.params['nodename']
        self.nodedescription = module.params['nodedescription']
        self.apikey = module.params['apikey']
        self.joined = module.params['joined']
        self.config = module.params['config']
        self.node = self.getNodeID()

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

    def getNodeID(self):
        """
        Gets local ZeroTier Network ID
        """
        fh = open('/var/lib/zerotier-one/identity.public', 'r')
        node = fh.readline().split(":")[0]
        fh.close()
        return node

    def getJoinStatus(self):
        """
        Checks if node has joined the target network
        """
        if os.path.exists("/var/lib/zerotier-one/networks.d/" + self.network + '.conf'):
          return True
        else:
          return False

    def joinNetwork(self):
        """
        Join node to network
        """
        result =  self.module.run_command(['zerotier-cli', 'join', self.network])
        self.result['changed'] = True
        return result

    def leaveNetwork(self):
        """
        Removes node from network
        """
        result = self.module.run_command(['zerotier-cli', 'leave', self.network])
        self.result['changed'] = True
        return result

    def setNodeConfig(self, config):
        """
        Sets node configuration
        """
        api_url = self.api_url + '/api/network/' + self.network + '/member/' + self.node
        api_auth = {'Authorization': 'bearer ' + self.apikey, 'Content-Type': 'application/json'}
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

    def getNodeConfig(self):
        """
        Gets node configuration
        """
        api_url = self.api_url + '/api/network/' + self.network + '/member/' + self.node
        api_auth = {'Authorization': 'bearer ' + self.apikey, 'Content-Type': 'application/json'}
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

    def buildNodeConfig(self):
        current_full_node_config = self.getNodeConfig()

        # Seperate the config key for clarity
        node_config = current_full_node_config['config']
        node_config.update(self.config)

        # Set config key
        if node_config != current_full_node_config['config']:
            self.result['changed'] = True
            current_full_node_config['config'] = node_config

        # Set some additional variables
        if current_full_node_config['hidden'] != self.hidden:
            self.result['changed'] = True
            current_full_node_config['hidden'] = self.hidden
        if current_full_node_config['name'] != self.nodename:
            self.result['changed'] = True
            current_full_node_config['name'] = self.nodename
        if current_full_node_config['description'] != self.nodedescription:
            self.result['changed'] = True
            current_full_node_config['description'] = self.nodedescription

        # Send it away
        self.setNodeConfig(current_full_node_config)

    def checkAPIKey(self):
            """
            Check if ZeroTier API Key works
            """
            api_url = self.api_url + '/api/network/' + self.network
            api_auth = {'Authorization': 'bearer ' + self.apikey, 'Content-Type': 'application/json'}
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

    def applyJoinStatus(self):
        if self.getZeroTierInstallStatus():
            if self.joined and not self.getJoinStatus():
                self.joinNetwork()
            elif not self.joined and self.getJoinStatus():
                self.leaveNetwork()
            return True
        else:
            self.module.fail_json(changed=False,
                                  msg="ZeroTier installation cannot be located in $PATH. Check your installation.")

def main():
    ssh_defaults = dict(
        bits=0,
        type='rsa',
        passphrase=None,
        comment='ansible-generated on %s' % socket.gethostname()
    )
    module = AnsibleModule(
        argument_spec=dict(
            name=dict(type='str', required=True),
            nodename=dict(type='str', required=False, default=""),
            nodedescription=dict(type='str', required=False, default=""),
            config=dict(type='dict', required=False, default={}),
            hidden=dict(type='bool', required=False, default=False),
            joined=dict(type='bool', required=False, default=True),
            apikey=dict(type='str', required=False, default=""),
        ),
        supports_check_mode=True,
    )
    zerotier = ZeroTierNode(module)
    # Set Join or not joined
    zerotier.applyJoinStatus()
    time.sleep(15)

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
