#
#  Copyright 2019 The FATE Authors. All Rights Reserved.
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#

import typing
from typing import Iterable

# noinspection PyPackageRequirements
from pyspark import SparkContext

from fate_arch.abc import AddressABC
from fate_arch.abc import CSessionABC
from fate_arch.common import file_utils, Party
from fate_arch.computing.spark import from_hdfs, from_rdd
from fate_arch.federation.spark import FederationEngine, MQ, RabbitManager
from fate_arch.session._parties_util import _FederationParties


class Session(CSessionABC):
    """
    manage RDDTable
    """

    def __init__(self, session_id):
        self._session_id = session_id

    def load(self, address: AddressABC, partitions, schema, **kwargs):
        from fate_arch.storage.address import HDFSAddress
        if isinstance(address, HDFSAddress):
            table = from_hdfs(paths=address.path, partitions=partitions)
            table.schema = schema
            return table
        from fate_arch.storage.address import FileAddress
        if isinstance(address, FileAddress):
            return address
        raise NotImplementedError(f"address type {type(address)} not supported with spark backend")

    def _init_federation(self, federation_session_id: str,
                         party: Party,
                         parties: typing.MutableMapping[str, typing.List[Party]],
                         rabbit_manager: RabbitManager, mq: MQ):
        if self._federation_session is not None:
            raise RuntimeError("federation session already initialized")
        self._federation_session = FederationEngine(federation_session_id, party, mq, rabbit_manager)
        self._federation_parties = _FederationParties(party, parties)

    def init_federation(self, federation_session_id: str, runtime_conf: dict, server_conf: typing.Optional[str] = None,
                        **kwargs):
        if server_conf is None:
            _path = file_utils.get_project_base_directory() + "/conf/server_conf.json"
            server_conf = file_utils.load_json_conf(_path)
        mq_conf = server_conf.get('rabbitmq')
        rabbitmq_conf = mq_conf.get("self")

        host = rabbitmq_conf.get("host")
        port = rabbitmq_conf.get("port")
        mng_port = rabbitmq_conf.get("mng_port")
        base_user = rabbitmq_conf.get('user')
        base_password = rabbitmq_conf.get('password')

        federation_info = runtime_conf.get("job_parameters", {}).get("federation_info", {})
        union_name = federation_info.get('union_name')
        policy_id = federation_info.get("policy_id")

        rabbit_manager = RabbitManager(base_user, base_password, f"{host}:{mng_port}")
        rabbit_manager.create_user(union_name, policy_id)
        mq = MQ(host, port, union_name, policy_id, mq_conf)
        party, parties = self._parse_runtime_conf(runtime_conf)
        return self._init_federation(federation_session_id, party, parties, rabbit_manager, mq)

    def parallelize(self, data: Iterable, partition: int, include_key: bool, **kwargs):
        _iter = data if include_key else enumerate(data)
        rdd = SparkContext.getOrCreate().parallelize(_iter, partition)
        return from_rdd(rdd)

    def _get_session_id(self):
        return self._session_id

    def _get_federation(self):
        return self._federation_session

    def _get_federation_parties(self):
        return self._federation_parties

    def cleanup(self, name, namespace):
        pass

    def stop(self):
        pass

    def kill(self):
        pass
