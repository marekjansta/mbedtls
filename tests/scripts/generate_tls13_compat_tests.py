#!/usr/bin/env python3

# generate_tls13_compat_tests.py
#
# Copyright The Mbed TLS Contributors
# SPDX-License-Identifier: Apache-2.0
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Generate TLSv1.3 Compat test cases

"""

import sys
import os
import abc
import argparse
import itertools
from collections import namedtuple

# define certificates configuration entry
Certificate = namedtuple("Certificate", ['cafile', 'certfile', 'keyfile'])
# define the certificate parameters for signature algorithms
CERTIFICATES = {
    'ecdsa_secp256r1_sha256': Certificate('data_files/test-ca2.crt',
                                          'data_files/ecdsa_secp256r1.crt',
                                          'data_files/ecdsa_secp256r1.key'),
    'ecdsa_secp384r1_sha384': Certificate('data_files/test-ca2.crt',
                                          'data_files/ecdsa_secp384r1.crt',
                                          'data_files/ecdsa_secp384r1.key'),
    'ecdsa_secp521r1_sha512': Certificate('data_files/test-ca2.crt',
                                          'data_files/ecdsa_secp521r1.crt',
                                          'data_files/ecdsa_secp521r1.key'),
    'rsa_pss_rsae_sha256': Certificate('data_files/test-ca_cat12.crt',
                                       'data_files/server2-sha256.crt', 'data_files/server2.key'
                                       )
}

CIPHER_SUITE_IANA_VALUE = {
    "TLS_AES_128_GCM_SHA256": 0x1301,
    "TLS_AES_256_GCM_SHA384": 0x1302,
    "TLS_CHACHA20_POLY1305_SHA256": 0x1303,
    "TLS_AES_128_CCM_SHA256": 0x1304,
    "TLS_AES_128_CCM_8_SHA256": 0x1305
}

SIG_ALG_IANA_VALUE = {
    "ecdsa_secp256r1_sha256": 0x0403,
    "ecdsa_secp384r1_sha384": 0x0503,
    "ecdsa_secp521r1_sha512": 0x0603,
    'rsa_pss_rsae_sha256': 0x0804,
}

NAMED_GROUP_IANA_VALUE = {
    'secp256r1': 0x17,
    'secp384r1': 0x18,
    'secp521r1': 0x19,
    'x25519': 0x1d,
    'x448': 0x1e,
}

HRR_CIPHER_SUITE_VALUE = {
    "TLS_AES_256_GCM_SHA384": 0x1302,
}

HRR_SIG_ALG_VALUE = {
    "ecdsa_secp384r1_sha384": 0x0503,
}

class TLSProgram(metaclass=abc.ABCMeta):
    """
    Base class for generate server/client command.
    """
    # pylint: disable=too-many-arguments
    def __init__(self, ciphersuite=None, signature_algorithm=None, named_group=None, peer_named_group=None,
                 is_hrr=False, cert_sig_alg=None, compat_mode=True):
        self._ciphers = []
        self._sig_algs = []
        self._named_groups = []
        self._peer_named_group = peer_named_group
        self._is_hrr = is_hrr
        self._cert_sig_algs = []
        if ciphersuite:
            self.add_ciphersuites(ciphersuite)
        if named_group:
            self.add_named_groups(named_group)
        if signature_algorithm:
            self.add_signature_algorithms(signature_algorithm)
        if cert_sig_alg:
            self.add_cert_signature_algorithms(cert_sig_alg)
        self._compat_mode = compat_mode

    # add_ciphersuites should not override by sub class
    def add_ciphersuites(self, *ciphersuites):
        self._ciphers.extend(
            [cipher for cipher in ciphersuites if cipher not in self._ciphers])

    # add_signature_algorithms should not override by sub class
    def add_signature_algorithms(self, *signature_algorithms):
        self._sig_algs.extend(
            [sig_alg for sig_alg in signature_algorithms if sig_alg not in self._sig_algs])

    # add_named_groups should not override by sub class
    def add_named_groups(self, *named_groups):
        self._named_groups.extend(
            [named_group for named_group in named_groups if named_group not in self._named_groups])

    # add_cert_signature_algorithms should not override by sub class
    def add_cert_signature_algorithms(self, *signature_algorithms):
        self._cert_sig_algs.extend(
            [sig_alg for sig_alg in signature_algorithms if sig_alg not in self._cert_sig_algs])

    @abc.abstractmethod
    def pre_checks(self):
        return []

    @abc.abstractmethod
    def cmd(self):
        if not self._cert_sig_algs:
            self._cert_sig_algs = list(CERTIFICATES.keys())

    @abc.abstractmethod
    def post_checks(self):
        return []


class OpenSSLServ(TLSProgram):
    """
    Generate test commands for OpenSSL server.
    """

    NAMED_GROUP = {
        'secp256r1': 'P-256',
        'secp384r1': 'P-384',
        'secp521r1': 'P-521',
        'x25519': 'X25519',
        'x448': 'X448',
    }

    def cmd(self):
        super().cmd()
        ret = ['$O_NEXT_SRV_NO_CERT']
        for _, cert, key in map(lambda sig_alg: CERTIFICATES[sig_alg], self._cert_sig_algs):
            ret += ['-cert {cert} -key {key}'.format(cert=cert, key=key)]
        ret += ['-accept $SRV_PORT']

        if not self._is_hrr:
            if self._ciphers:
                ciphersuites = ':'.join(self._ciphers)
                ret += ["-ciphersuites {ciphersuites}".format(ciphersuites=ciphersuites)]

            if self._sig_algs:
                signature_algorithms = set(self._sig_algs + self._cert_sig_algs)
                signature_algorithms = ':'.join(signature_algorithms)
                ret += ["-sigalgs {signature_algorithms}".format(
                    signature_algorithms=signature_algorithms)]

        if self._named_groups:
            named_groups = ':'.join(
                map(lambda named_group: self.NAMED_GROUP[named_group], self._named_groups))
            ret += ["-groups {named_groups}".format(named_groups=named_groups)]

        ret += ['-msg -tls1_3 -num_tickets 0 -no_resume_ephemeral -no_cache']
        if not self._compat_mode:
            ret += ['-no_middlebox']

        return ' '.join(ret)

    def pre_checks(self):
        return ["requires_openssl_tls1_3"]

    def post_checks(self):
        return ['-c "HTTP/1.0 200 ok"']


class GnuTLSServ(TLSProgram):
    """
    Generate test commands for GnuTLS server.
    """

    CIPHER_SUITE = {
        'TLS_AES_256_GCM_SHA384': [
            'AES-256-GCM',
            'SHA384',
            'AEAD'],
        'TLS_AES_128_GCM_SHA256': [
            'AES-128-GCM',
            'SHA256',
            'AEAD'],
        'TLS_CHACHA20_POLY1305_SHA256': [
            'CHACHA20-POLY1305',
            'SHA256',
            'AEAD'],
        'TLS_AES_128_CCM_SHA256': [
            'AES-128-CCM',
            'SHA256',
            'AEAD'],
        'TLS_AES_128_CCM_8_SHA256': [
            'AES-128-CCM-8',
            'SHA256',
            'AEAD']}

    SIGNATURE_ALGORITHM = {
        'ecdsa_secp256r1_sha256': ['SIGN-ECDSA-SECP256R1-SHA256'],
        'ecdsa_secp521r1_sha512': ['SIGN-ECDSA-SECP521R1-SHA512'],
        'ecdsa_secp384r1_sha384': ['SIGN-ECDSA-SECP384R1-SHA384'],
        'rsa_pss_rsae_sha256': ['SIGN-RSA-PSS-RSAE-SHA256']}

    NAMED_GROUP = {
        'secp256r1': ['GROUP-SECP256R1'],
        'secp384r1': ['GROUP-SECP384R1'],
        'secp521r1': ['GROUP-SECP521R1'],
        'x25519': ['GROUP-X25519'],
        'x448': ['GROUP-X448'],
    }

    def pre_checks(self):
        return ["requires_gnutls_tls1_3",
                "requires_gnutls_next_no_ticket",
                "requires_gnutls_next_disable_tls13_compat", ]

    def post_checks(self):
        return ['-c "HTTP/1.0 200 OK"']

    def cmd(self):
        super().cmd()
        ret = ['$G_NEXT_SRV_NO_CERT', '--http',
               '--disable-client-cert', '--debug=4']

        for _, cert, key in map(lambda sig_alg: CERTIFICATES[sig_alg], self._cert_sig_algs):
            ret += ['--x509certfile {cert} --x509keyfile {key}'.format(
                cert=cert, key=key)]

        priority_string_list = []

        def update_priority_string_list(items, map_table):
            for item in items:
                for i in map_table[item]:
                    if i not in priority_string_list:
                        yield i

        if self._is_hrr:
            priority_string_list.extend(
                        ['CIPHER-ALL', 'SIGN-ALL', 'MAC-ALL'])
        else:
            if self._ciphers:
                priority_string_list.extend(update_priority_string_list(
                    self._ciphers, self.CIPHER_SUITE))
            else:
                priority_string_list.append('CIPHER-ALL')

            if self._sig_algs:
                signature_algorithms = set(self._sig_algs + self._cert_sig_algs)
                priority_string_list.extend(update_priority_string_list(
                    signature_algorithms, self.SIGNATURE_ALGORITHM))
            else:
                priority_string_list.append('SIGN-ALL')


        if self._named_groups:
            priority_string_list.extend(update_priority_string_list(
                self._named_groups, self.NAMED_GROUP))
        else:
            priority_string_list.append('GROUP-ALL')

        priority_string_list = ['NONE'] + \
            sorted(priority_string_list) + ['VERS-TLS1.3']

        priority_string = ':+'.join(priority_string_list)
        priority_string += ':%NO_TICKETS'

        if not self._compat_mode:
            priority_string += [':%DISABLE_TLS13_COMPAT_MODE']

        ret += ['--priority={priority_string}'.format(
            priority_string=priority_string)]
        ret = ' '.join(ret)
        return ret


class MbedTLSCli(TLSProgram):
    """
    Generate test commands for mbedTLS client.
    """

    CIPHER_SUITE = {
        'TLS_AES_256_GCM_SHA384': 'TLS1-3-AES-256-GCM-SHA384',
        'TLS_AES_128_GCM_SHA256': 'TLS1-3-AES-128-GCM-SHA256',
        'TLS_CHACHA20_POLY1305_SHA256': 'TLS1-3-CHACHA20-POLY1305-SHA256',
        'TLS_AES_128_CCM_SHA256': 'TLS1-3-AES-128-CCM-SHA256',
        'TLS_AES_128_CCM_8_SHA256': 'TLS1-3-AES-128-CCM-8-SHA256'}

    def cmd(self):
        super().cmd()
        ret = ['$P_CLI']
        ret += ['server_addr=127.0.0.1', 'server_port=$SRV_PORT',
                'debug_level=4', 'force_version=tls13']
        ret += ['ca_file={cafile}'.format(
            cafile=CERTIFICATES[self._cert_sig_algs[0]].cafile)]

        if not self._is_hrr:
            if self._ciphers:
                ciphers = ','.join(
                    map(lambda cipher: self.CIPHER_SUITE[cipher], self._ciphers))
                ret += ["force_ciphersuite={ciphers}".format(ciphers=ciphers)]

            if self._sig_algs + self._cert_sig_algs:
                ret += ['sig_algs={sig_algs}'.format(
                    sig_algs=','.join(set(self._sig_algs + self._cert_sig_algs)))]

        if self._named_groups:
            if self._is_hrr:
                for sig_alg in self._sig_algs:
                    if sig_alg in ('ecdsa_secp256r1_sha256',
                                   'ecdsa_secp384r1_sha384',
                                   'ecdsa_secp521r1_sha512'):
                        self.add_named_groups(sig_alg.split('_')[1])
                self.add_named_groups(self._peer_named_group)
            named_groups = ','.join(self._named_groups)
            ret += ["curves={named_groups}".format(named_groups=named_groups)]

        ret = ' '.join(ret)
        return ret

    def pre_checks(self):
        ret = ['requires_config_enabled MBEDTLS_DEBUG_C',
               'requires_config_enabled MBEDTLS_SSL_CLI_C',
               'requires_config_enabled MBEDTLS_SSL_PROTO_TLS1_3']

        if self._compat_mode:
            ret += ['requires_config_enabled MBEDTLS_SSL_TLS1_3_COMPATIBILITY_MODE']

        if 'rsa_pss_rsae_sha256' in self._sig_algs + self._cert_sig_algs:
            ret.append(
                'requires_config_enabled MBEDTLS_X509_RSASSA_PSS_SUPPORT')
        return ret

    def post_checks(self):
        check_strings = []
        if self._ciphers:
            check_strings.append(
                "server hello, chosen ciphersuite: ( {:04x} ) - {}".format(
                    CIPHER_SUITE_IANA_VALUE[self._ciphers[0]],
                    self.CIPHER_SUITE[self._ciphers[0]]))
        if self._sig_algs:
            check_strings.append(
                "Certificate Verify: Signature algorithm ( {:04x} )".format(
                    SIG_ALG_IANA_VALUE[self._sig_algs[0]]))

        for named_group in self._named_groups:
            check_strings += ['NamedGroup: {named_group} ( {iana_value:x} )'.format(
                                named_group=named_group,
                                iana_value=NAMED_GROUP_IANA_VALUE[named_group])]

        check_strings.append("Verifying peer X.509 certificate... ok")
        return ['-c "{}"'.format(i) for i in check_strings]

    # pylint: disable=C0330
    def post_hrr_checks(self):
        check_strings = ["NamedGroup: {group}".format(group=self._named_groups[0]),
                         "NamedGroup: {group}".format(group=self._named_groups[-1]),
                        "<= ssl_tls13_process_server_hello ( HelloRetryRequest )",
                         "Verifying peer X.509 certificate... ok", ]
        return ['-c "{}"'.format(i) for i in check_strings]


SERVER_CLASSES = {'OpenSSL': OpenSSLServ, 'GnuTLS': GnuTLSServ}
CLIENT_CLASSES = {'mbedTLS': MbedTLSCli}


def generate_compat_test(server=None, client=None, cipher=None, sig_alg=None, named_group=None):
    """
    Generate test case with `ssl-opt.sh` format.
    """
    name = 'TLS 1.3 {client[0]}->{server[0]}: {cipher},{named_group},{sig_alg}'.format(
        client=client, server=server, cipher=cipher, sig_alg=sig_alg, named_group=named_group)

    server_object = SERVER_CLASSES[server](ciphersuite=cipher,
                                           named_group=named_group,
                                           signature_algorithm=sig_alg,
                                           cert_sig_alg=sig_alg)
    client_object = CLIENT_CLASSES[client](ciphersuite=cipher,
                                           named_group=named_group,
                                           signature_algorithm=sig_alg,
                                           cert_sig_alg=sig_alg)

    cmd = ['run_test "{}"'.format(name), '"{}"'.format(
        server_object.cmd()), '"{}"'.format(client_object.cmd()), '0']
    cmd += server_object.post_checks()
    cmd += client_object.post_checks()
    cmd += ['-C "received HelloRetryRequest message"']
    prefix = ' \\\n' + (' '*9)
    cmd = prefix.join(cmd)
    return '\n'.join(server_object.pre_checks() + client_object.pre_checks() + [cmd])

# pylint: disable=too-many-arguments,C0330
def generate_compat_hrr_test(server=None, client=None, cipher=None, sig_alg=None,
                             client_named_group=None, server_named_group=None):
    """
    Generate test case with `ssl-opt.sh` format.
    """
    name = 'TLS 1.3 {client[0]}->{server[0]}: HRR {client_named_group} -> {server_named_group}'.format(
            client=client, server=server, client_named_group=client_named_group, server_named_group=server_named_group)
    server_object = SERVER_CLASSES[server](cipher, sig_alg, server_named_group, client_named_group, True)
    client_object = CLIENT_CLASSES[client](cipher, sig_alg, client_named_group, server_named_group, True)

    cmd = ['run_test "{}"'.format(name), '"{}"'.format(
        server_object.cmd()), '"{}"'.format(client_object.cmd()), '0']
    cmd += server_object.post_checks()
    cmd += client_object.post_hrr_checks()
    prefix = ' \\\n' + (' '*9)
    cmd = prefix.join(cmd)
    return '\n'.join(server_object.pre_checks() + client_object.pre_checks() + [cmd])


SSL_OUTPUT_HEADER = '''#!/bin/sh

# {filename}
#
# Copyright The Mbed TLS Contributors
# SPDX-License-Identifier: Apache-2.0
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# Purpose
#
# List TLS1.3 compat test cases. They are generated by
# `generate_tls13_compat_tests.py {parameter} -o {filename}`.
#
# PLEASE DO NOT EDIT THIS FILE. IF NEEDED, PLEASE MODIFY `generate_tls13_compat_tests.py`
# AND REGENERATE THIS FILE.
#
'''


# pylint: disable=too-many-branches
def main():
    """
    Main function of this program
    """
    parser = argparse.ArgumentParser()

    parser.add_argument('-o', '--output', nargs='?',
                        default=None, help='Output file path if `-a` was set')

    parser.add_argument('-a', '--generate-all-tls13-compat-tests', action='store_true',
                        default=False, help='Generate all available tls13 compat tests')

    parser.add_argument('--list-ciphers', action='store_true',
                        default=False, help='List supported ciphersuites')

    parser.add_argument('--list-sig-algs', action='store_true',
                        default=False, help='List supported signature algorithms')

    parser.add_argument('--list-named-groups', action='store_true',
                        default=False, help='List supported named groups')

    parser.add_argument('--list-servers', action='store_true',
                        default=False, help='List supported TLS servers')

    parser.add_argument('--list-clients', action='store_true',
                        default=False, help='List supported TLS Clients')

    parser.add_argument('server', choices=SERVER_CLASSES.keys(), nargs='?',
                        default=list(SERVER_CLASSES.keys())[0],
                        help='Choose TLS server program for test')
    parser.add_argument('client', choices=CLIENT_CLASSES.keys(), nargs='?',
                        default=list(CLIENT_CLASSES.keys())[0],
                        help='Choose TLS client program for test')
    parser.add_argument('cipher', choices=CIPHER_SUITE_IANA_VALUE.keys(), nargs='?',
                        default=list(CIPHER_SUITE_IANA_VALUE.keys())[0],
                        help='Choose cipher suite for test')
    parser.add_argument('sig_alg', choices=SIG_ALG_IANA_VALUE.keys(), nargs='?',
                        default=list(SIG_ALG_IANA_VALUE.keys())[0],
                        help='Choose cipher suite for test')
    parser.add_argument('named_group', choices=NAMED_GROUP_IANA_VALUE.keys(), nargs='?',
                        default=list(NAMED_GROUP_IANA_VALUE.keys())[0],
                        help='Choose cipher suite for test')

    args = parser.parse_args()

    def get_all_test_cases():
        # Generate normal compat test cases
        for cipher, sig_alg, named_group, server, client in \
            itertools.product(CIPHER_SUITE_IANA_VALUE.keys(),
                              SIG_ALG_IANA_VALUE.keys(),
                              NAMED_GROUP_IANA_VALUE.keys(),
                              SERVER_CLASSES.keys(),
                              CLIENT_CLASSES.keys()):
            yield generate_compat_test(cipher=cipher, sig_alg=sig_alg, named_group=named_group,
                                       server=server, client=client)
        for cipher, sig_alg, client_named_group, server_named_group, server, client in \
            itertools.product(HRR_CIPHER_SUITE_VALUE.keys(), HRR_SIG_ALG_VALUE.keys(),
                              NAMED_GROUP_IANA_VALUE.keys(), NAMED_GROUP_IANA_VALUE.keys(),
                              SERVER_CLASSES.keys(), CLIENT_CLASSES.keys()):
            if client_named_group != server_named_group:
                yield generate_compat_hrr_test(cipher=cipher, sig_alg=sig_alg,
                                               client_named_group=client_named_group,
                                               server_named_group=server_named_group,
                                               server=server, client=client)

    if args.generate_all_tls13_compat_tests:
        if args.output:
            with open(args.output, 'w', encoding="utf-8") as f:
                f.write(SSL_OUTPUT_HEADER.format(
                    filename=os.path.basename(args.output), parameter='-a'))
                f.write('\n\n'.join(get_all_test_cases()))
                f.write('\n')
        else:
            print('\n\n'.join(get_all_test_cases()))
        return 0

    if args.list_ciphers or args.list_sig_algs or args.list_named_groups \
            or args.list_servers or args.list_clients:
        if args.list_ciphers:
            print(*CIPHER_SUITE_IANA_VALUE.keys())
        if args.list_sig_algs:
            print(*SIG_ALG_IANA_VALUE.keys())
        if args.list_named_groups:
            print(*NAMED_GROUP_IANA_VALUE.keys())
        if args.list_servers:
            print(*SERVER_CLASSES.keys())
        if args.list_clients:
            print(*CLIENT_CLASSES.keys())
        return 0

    if args.generate_all_tls13_compat_tests:
        print(generate_compat_test(server=args.server, client=args.client, sig_alg=args.sig_alg,
                                   cipher=args.cipher, named_group=args.named_group))

    return 0


if __name__ == "__main__":
    sys.exit(main())
