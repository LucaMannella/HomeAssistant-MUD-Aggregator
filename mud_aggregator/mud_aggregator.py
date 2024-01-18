""" Platform for generating and exposing a MUD file. """
from __future__ import annotations
from datetime import datetime
import json
import logging
import os
import random
import socket

from getmac import get_mac_address as gma
import voluptuous as vol
from scapy.all import Ether, IP, UDP, BOOTP, DHCP, sendp
import shutil

from . import DOMAIN, constants as c, util_network as nu

_LOGGER = logging.getLogger(__name__)

# Core paths (e.g., in Devcontainer)
_CORE_DEFAULT_COMPONENTS_PATH = "./homeassistant/components/"
_CORE_CUSTOM_COMPONENTS_PATH = "./config/custom_components/"
_CORE_STORAGE_PATH = "./config/www/MUD/"

# Filenames
_DRAFT_FILENAME = "mud_draft.json"
_FILENAME = "hass_mud_file"
_MUD_FILENAME = _FILENAME + ".json"
_SIGNATURE_FILENAME = _FILENAME + ".p7s"
_CERTIFICATE_FILENAME = "cert.pem"
_KEY_FILENAME = "key.pem"


class MUDAggregator:
    """This class is able to create and expose a MUD file."""

    def __init__(self, deployment: str = c.DEPLOY_CORE) -> None:
        self._deployment = deployment
        if self._deployment == c.DEPLOY_CORE:
            self._STORAGE_PATH = _CORE_STORAGE_PATH
            self._DEFAULT_COMPONENTS_PATH = _CORE_DEFAULT_COMPONENTS_PATH
            self._CUSTOM_COMPONENTS_PATH = _CORE_CUSTOM_COMPONENTS_PATH
            self._LOCAL_EXTENTION_PATH = _CORE_CUSTOM_COMPONENTS_PATH + "mud_aggregator/"
        else:
            # HAss OS paths
            self._STORAGE_PATH = "/config/www/MUD/"
            self._DEFAULT_COMPONENTS_PATH = "/homeassistant/components/"
            self._CUSTOM_COMPONENTS_PATH = "/config/custom_components/"
            self._LOCAL_EXTENTION_PATH = self._CUSTOM_COMPONENTS_PATH + "mud_aggregator/"
            # Installing openSSL on HAss OS --> maybe this command could not be given in HAss
            installed = os.system("apk add openssl")
            if not installed:
                _LOGGER.critical("Impossible to install OpenSSL")

        self._mud_draft = {}

        # Checking if the web server directory exists. If not is created.
        if not os.path.exists(self._STORAGE_PATH):
            _LOGGER.info("Creating web server folder: <%s>", self._STORAGE_PATH)
            os.makedirs(self._STORAGE_PATH)
        else:
            _LOGGER.debug("Web server folder already exists: <%s>", self._STORAGE_PATH)

    def generate_mud_file(self, integration_list: dict = None, sign: bool = True):
        """This function generates a MUD file starting from a template"""
        self._mud_draft = self._load_mud_draft()  # (Re)loading original draft
        inserted_rules = self._add_mud_rules(integration_list)

        mud_file_path = self._LOCAL_EXTENTION_PATH + _MUD_FILENAME
        if not os.path.exists(mud_file_path):
            mud_changed = True
        else:
            with open(mud_file_path, "r", encoding="utf-8") as inputfile:
                old_mud = json.load(inputfile)
                if "last-update" in old_mud["ietf-mud:mud"]:
                    # removing last-update timestamp if exists
                    del old_mud["ietf-mud:mud"]["last-update"]

                if self._mud_draft == old_mud:
                    mud_changed = False
                else:
                    mud_changed = True

        if mud_changed:
            # mud_draft["mud-url"] = "http://iot-device.example.com/dnsname"
            current_time = datetime.now().isoformat(timespec="seconds")
            self._mud_draft["ietf-mud:mud"]["last-update"] = current_time
            self._write_mud_file(sign)
        else:
            _LOGGER.debug("MUD file was not changed!")


    def _load_mud_draft(self) -> dict:
        draft = None
        # self._cwd = os.getcwd()
        file_name = self._LOCAL_EXTENTION_PATH + _DRAFT_FILENAME
        with open(file_name, "r", encoding="utf-8") as inputfile:
            draft = json.load(inputfile)
        return draft

    def _add_mud_rules(self, integration_list: dict = None) -> int:
        """Adding the ACLs to the MUD object."""
        inserted_rules = 0
        if integration_list:
            inserted_rules += self._add_rules_from_manifest(integration_list)
        inserted_rules += self._add_rules_from_folders()
        _LOGGER.info("Total rules inserted in the MUD file: %d", inserted_rules)
        return inserted_rules

    def _add_rules_from_manifest(self, integration_list: dict):
        """This method adds MUD snippets retrieving references from the manifest."""
        total_inserted_rules = 0
        for integration_name, integration_object in integration_list.items():
            manifest = integration_object.manifest
            if "mud_file" in manifest:
                mud_snippet = manifest["mud_file"]
                if mud_snippet.lower().startswith("http"):
                    _LOGGER.warning("MUD remotely stored not yet implemented!")
                else:
                    _LOGGER.debug("MUD snippet of <%s> is stored <%s>", integration_name, mud_snippet)
                    # adding to POSIX path
                    snippet_path = integration_object.file_path / mud_snippet
                    inserted_rules = self._add_rules_to_draft(snippet_path)
                    _LOGGER.debug("<%s> adds %d rules to the MUD file", integration_name, inserted_rules)
                    total_inserted_rules += inserted_rules
        return total_inserted_rules

    def _add_rules_from_folders(self):
        """This method takes the MUD snippets crossing integration folders."""
        total_inserted_rules = 0

        # Iterate over custom components directories
        _LOGGER.debug("Adding MUD snippets of custom_components")
        assert os.path.isdir(self._CUSTOM_COMPONENTS_PATH)
        for cur_path, dirs, files in os.walk(self._CUSTOM_COMPONENTS_PATH):
            if cur_path == self._CUSTOM_COMPONENTS_PATH:
                continue
            elif "__" in cur_path or ".git" in cur_path or DOMAIN in cur_path:
                continue

            if c.MUD_EXTRACT_FILENAME in files:
                _LOGGER.info("MUD information found in <%s>", cur_path)
                snippet_path = cur_path + "/" + c.MUD_EXTRACT_FILENAME
                inserted_rules = self._add_rules_to_draft(snippet_path)
                _LOGGER.debug("<%s> adds %d rules to the MUD file", cur_path, inserted_rules)
                total_inserted_rules += inserted_rules

        # Iterate over default components directories if available
        if self._deployment == c.DEPLOY_CORE:
            _LOGGER.debug("Adding MUD snippets of default integrations")
            assert os.path.isdir(self._DEFAULT_COMPONENTS_PATH)
            for cur_path, dirs, files in os.walk(self._DEFAULT_COMPONENTS_PATH):
                if cur_path == self._DEFAULT_COMPONENTS_PATH:
                    continue
                elif "__" in cur_path or ".git" in cur_path:
                    continue

                if c.MUD_EXTRACT_FILENAME in files:
                    _LOGGER.info("MUD information found in <%s>", cur_path)
                    snippet_path = cur_path + "/" + c.MUD_EXTRACT_FILENAME
                    inserted_rules = self._add_rules_to_draft(snippet_path)
                    _LOGGER.debug("<%s> adds %d rules to the MUD file", cur_path, inserted_rules)
                    total_inserted_rules += inserted_rules

        _LOGGER.info("%d rules were inserted in the MUD file", total_inserted_rules)
        return total_inserted_rules

    def _add_rules_to_draft(self, snippet_path) -> int:
        inserted_rules = 0

        if not os.path.isfile(snippet_path):
            _LOGGER.error("MUD snippet does not exists! Filepath: <%s>", snippet_path)
            return inserted_rules

        with open(snippet_path, "r", encoding="utf-8") as inputfile:
            try:
                mud_extract = json.load(inputfile)

                old_from_policies = self._mud_draft["ietf-mud:mud"]["from-device-policy"]["access-lists"]["access-list"]
                new_from_policies = mud_extract["ietf-mud:mud"]["from-device-policy"]["access-lists"]["access-list"]
                from_count = self._add_policies_if_not_exist(old_from_policies, new_from_policies, self._mud_draft["ietf-mud:mud"]["from-device-policy"]["access-lists"]["access-list"])

                old_to_policy = self._mud_draft["ietf-mud:mud"]["to-device-policy"]["access-lists"]["access-list"]
                new_to_policy = mud_extract["ietf-mud:mud"]["to-device-policy"]["access-lists"]["access-list"]
                to_count = self._add_policies_if_not_exist(old_to_policy, new_to_policy, self._mud_draft["ietf-mud:mud"]["to-device-policy"]["access-lists"]["access-list"])

                old_acls = self._mud_draft["ietf-access-control-list:acls"]["acl"]
                new_acls = mud_extract["ietf-access-control-list:acls"]["acl"]
                acl_count = self._add_acls_if_not_exist(old_acls, new_acls, self._mud_draft["ietf-access-control-list:acls"]["acl"])

                if (from_count + to_count) != acl_count:
                    _LOGGER.warning("The added snippet is inconsistent!")
                    inserted_rules = -1
                else:
                    inserted_rules = acl_count

            except json.decoder.JSONDecodeError as ex:
                _LOGGER.error("Error parsing the MUD snippet: <%s>", snippet_path)
                _LOGGER.error("Snippet Error: %s", ex)

        return inserted_rules

    def _add_policies_if_not_exist(self, old_policies, new_policies, target):
        """This method adds the <new_policies> inside <target> if they do not exist in <old_policies>.
        To verify the existence only the field name is checked."""
        count = 0
        exist = False
        for new_pol in new_policies:
            for old_pol in old_policies:
                if new_pol["name"] == old_pol["name"]:
                    exist = True
                    break
            if not exist:
                target.append({"name": new_pol["name"]})
                count += 1
        return count

    def _add_acls_if_not_exist(self, old_acls, new_acls, target):
        """This method adds the <new_acls> inside <target> if they do not exist in <old_acls>.
        To verify the existence only the field name is checked."""
        count = 0
        exist = False
        for new_acl in new_acls:
            for old_acl in old_acls:
                if new_acl["name"] == old_acl["name"]:
                    exist = True
                    break
            if not exist:
                target.append(new_acl)
                count += 1
        return count

    def _write_mud_file(self, sign=True):
        """Writing the new MUD file on a JSON file."""
        integration_mud_path = self._LOCAL_EXTENTION_PATH+_MUD_FILENAME
        with open(integration_mud_path, "w", encoding="utf-8") as outfile:
            json.dump(self._mud_draft, outfile, indent=2)
        _LOGGER.debug("MUD file generated inside integration folder for debug")

        if sign:
            _LOGGER.debug("Signing the MUD file")
            certificate_path = self._LOCAL_EXTENTION_PATH + _CERTIFICATE_FILENAME
            key_path = self._LOCAL_EXTENTION_PATH + _KEY_FILENAME

            if not os.path.exists(certificate_path) or not os.path.exists(key_path):
                _LOGGER.debug("Missing certificate (or private key). Creating now!")
                # generating certificate
                cert_command = 'openssl req -x509 -newkey rsa:4096 -sha256 -days 3650 -nodes -keyout '+key_path+' -out '+certificate_path+' -subj "/CN=HAss-MUD-Aggregator"'
                ok = os.system(cert_command)
                if ok == 0:
                    _LOGGER.debug("Certificate succesfully generated!")
                else:
                    _LOGGER.critical("Certificate not generated, will be impossible to sign the MUD file!")

            # Signing the generated MUD file (if the certificate is available)
            if os.path.exists(certificate_path) and os.path.exists(key_path):
                integration_signature_path = self._LOCAL_EXTENTION_PATH+_SIGNATURE_FILENAME
                sign_command = "openssl cms -sign -signer "+certificate_path+" -inkey "+key_path+" -in "+integration_mud_path+" -binary -outform DER -out "+integration_signature_path
                ok = os.system(sign_command)
                if ok == 0:
                    _LOGGER.debug("MUD file signed")
                    signature_storage_path = self._STORAGE_PATH + _SIGNATURE_FILENAME
                    shutil.copyfile(integration_signature_path, signature_storage_path)
                else:
                    _LOGGER.error("MUD file not signed!")

        if os.path.exists(self._STORAGE_PATH):
            mud_storage_path = self._STORAGE_PATH + _MUD_FILENAME
            shutil.copyfile(integration_mud_path, mud_storage_path)
            _LOGGER.warning("The MUD file is ready to be exposed!")
        else:
            _LOGGER.critical("There is no webserver folder!")

    def expose_mud_file(self, interface="eth0", mode="DHCP"):
        """Exposing the MUD file to the MUD manager."""

        if mode == "DHCP":
            _LOGGER.debug("Exposing the MUD file through DHCP")
            self.expose_MUD_file_DHCP(interface)
        elif mode == "LLDP":
            _LOGGER.debug("Exposing the MUD file through LLDP is not yet implemented")
        elif mode == "802.1AR":
            _LOGGER.debug("Exposing the MUD file inside a X.509 certificate through 802.1AR is not yet implemented")
        else:
            _LOGGER.error("MUD file not exposed, unrecognized mode!")

    def expose_MUD_file_DHCP(self, interface="eth0"):  # wlan0
        """This method expose the MUD file using the DHCP protocol."""
        HAss_mac = gma()
        byte_mac_addr = nu.mac_to_bytes(HAss_mac)

        hostname = socket.gethostname()
        # HAss_IP = socket.gethostbyname(hostname)
        HAss_IP = nu.get_ip()
        # HAss_IP = "192.168.7.242"

        # _LOGGER.debug("HAss MAC address is: %s", HAss_mac)
        # _LOGGER.debug("HAss IP address is: %s", HAss_IP)
        _LOGGER.debug("Hostname: %s --- Interface: <%s> --- IP: %s --- MAC: %s", hostname, interface, HAss_IP, HAss_mac)

        # _LOGGER.debug("Releasing IP address...")
        # self._send_dchp_message("release", HAss_IP, byte_mac_addr, hostname, interface)

        MUD_URL = "http://"+HAss_IP+":8123/local/MUD/hass_mud_file.json"
        _LOGGER.debug("Trying to expose the MUD URL: %s", MUD_URL)
        # _LOGGER.debug("Renewing IP address with associated MUD file")
        self.send_dchp_message("request", HAss_IP, byte_mac_addr, hostname, interface, MUD_URL)

        _LOGGER.debug("MUD URL Exposed!")
        return

        # packet = (
        #     Ether(dst="ff:ff:ff:ff:ff:ff")   IP(src=HAss_IP, dst="255.255.255.255")   UDP(sport=68, dport=67) /
        #     BOOTP( chaddr=self.mac_to_bytes(HAss_mac), xid=random.randint(1, 2**32-1), ) /
        #     # DHCP(options=[("message-type", "discover"), ("mud-url", MUD_URL), "end"])
        #     DHCP(options=[("message-type", "discover"), "end"])
        # )


    def send_dchp_message(self, message_type, device_IP, byte_mac_addr, hostname, interface_name, mud_url=None, verbose=True):
        ## MT: discover -> The first message of a DHCP flow -> Can I have a DHCP address?
        ## MT: request -> The third message of a DHCP flow -> I would like to accept your offer
        ## MT: release -> I do not want my address anymore

        client_id = bytearray(byte_mac_addr)
        client_id.insert(0, 1)
        client_id = bytes(client_id)

        dhcp_options = [("message-type", message_type)]
        dhcp_options.append(("client_id", client_id))
        if not message_type == "release":
            dhcp_options.append(("requested_addr", device_IP))
        dhcp_options.append(("hostname", hostname))
        if mud_url:
            dhcp_options.append(("mud-url", mud_url))
        dhcp_options.append("end")
        dhcp_object = DHCP(options=dhcp_options)

        packet = (
            Ether(dst="ff:ff:ff:ff:ff:ff") /
            IP(src="0.0.0.0", dst="255.255.255.255") /  # src=device_ip
            UDP(sport=68, dport=67) /
            BOOTP(
                chaddr=byte_mac_addr,
                xid=random.randint(1, 2**32-1),  # Random integer required by DHCP
            ) /
            dhcp_object
        )
        _LOGGER.debug("Packet to send:\n %s", packet.__str__)
        rv = sendp(packet, iface=interface_name, verbose=verbose, return_packets=True)
        return rv


    def print_mud_draft(self):
        """Printing MUD elements."""

        _LOGGER.debug("Printing from policies")
        access_list = self._mud_draft["ietf-mud:mud"]["from-device-policy"]["access-lists"]["access-list"]
        for x in access_list:
            _LOGGER.debug(x)

        _LOGGER.debug("Printing to policies")
        access_list = self._mud_draft["ietf-mud:mud"]["to-device-policy"]["access-lists"]["access-list"]
        for x in access_list:
            _LOGGER.debug(x)

        _LOGGER.debug("Printing ACLs")
        acls = self._mud_draft["ietf-access-control-list:acls"]["acl"]
        for x in acls:
            _LOGGER.debug(x)
