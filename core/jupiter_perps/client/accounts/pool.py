import typing
from dataclasses import dataclass
from construct import Construct
from solders.pubkey import Pubkey
from solana.rpc.async_api import AsyncClient
from solana.rpc.commitment import Commitment
import borsh_construct as borsh
from anchorpy.coder.accounts import ACCOUNT_DISCRIMINATOR_SIZE
from anchorpy.error import AccountInvalidDiscriminator
from anchorpy.utils.rpc import get_multiple_accounts
from anchorpy.borsh_extension import BorshPubkey
from ..program_id import PROGRAM_ID
from .. import types


class PoolJSON(typing.TypedDict):
    name: str
    custodies: list[str]
    aum_usd: int
    limit: types.limit.LimitJSON
    fees: types.fees.FeesJSON
    pool_apr: types.pool_apr.PoolAprJSON
    max_request_execution_sec: int
    bump: int
    lp_token_bump: int
    inception_time: int
    parameter_update_oracle: types.secp256k1_pubkey.Secp256k1PubkeyJSON
    aum_usd_updated_at: int


@dataclass
class Pool:
    discriminator: typing.ClassVar = b"\xf1\x9am\x04\x11\xb1m\xbc"
    layout: typing.ClassVar = borsh.CStruct(
        "name" / borsh.String,
        "custodies" / borsh.Vec(typing.cast(Construct, BorshPubkey)),
        "aum_usd" / borsh.U128,
        "limit" / types.limit.Limit.layout,
        "fees" / types.fees.Fees.layout,
        "pool_apr" / types.pool_apr.PoolApr.layout,
        "max_request_execution_sec" / borsh.I64,
        "bump" / borsh.U8,
        "lp_token_bump" / borsh.U8,
        "inception_time" / borsh.I64,
        "parameter_update_oracle" / types.secp256k1_pubkey.Secp256k1Pubkey.layout,
        "aum_usd_updated_at" / borsh.I64,
    )
    name: str
    custodies: list[Pubkey]
    aum_usd: int
    limit: types.limit.Limit
    fees: types.fees.Fees
    pool_apr: types.pool_apr.PoolApr
    max_request_execution_sec: int
    bump: int
    lp_token_bump: int
    inception_time: int
    parameter_update_oracle: types.secp256k1_pubkey.Secp256k1Pubkey
    aum_usd_updated_at: int

    @classmethod
    async def fetch(
        cls,
        conn: AsyncClient,
        address: Pubkey,
        commitment: typing.Optional[Commitment] = None,
        program_id: Pubkey = PROGRAM_ID,
    ) -> typing.Optional["Pool"]:
        resp = await conn.get_account_info(address, commitment=commitment)
        info = resp.value
        if info is None:
            return None
        if info.owner != program_id:
            raise ValueError("Account does not belong to this program")
        bytes_data = info.data
        return cls.decode(bytes_data)

    @classmethod
    async def fetch_multiple(
        cls,
        conn: AsyncClient,
        addresses: list[Pubkey],
        commitment: typing.Optional[Commitment] = None,
        program_id: Pubkey = PROGRAM_ID,
    ) -> typing.List[typing.Optional["Pool"]]:
        infos = await get_multiple_accounts(conn, addresses, commitment=commitment)
        res: typing.List[typing.Optional["Pool"]] = []
        for info in infos:
            if info is None:
                res.append(None)
                continue
            if info.account.owner != program_id:
                raise ValueError("Account does not belong to this program")
            res.append(cls.decode(info.account.data))
        return res

    @classmethod
    def decode(cls, data: bytes) -> "Pool":
        if data[:ACCOUNT_DISCRIMINATOR_SIZE] != cls.discriminator:
            raise AccountInvalidDiscriminator(
                "The discriminator for this account is invalid"
            )
        dec = Pool.layout.parse(data[ACCOUNT_DISCRIMINATOR_SIZE:])
        return cls(
            name=dec.name,
            custodies=dec.custodies,
            aum_usd=dec.aum_usd,
            limit=types.limit.Limit.from_decoded(dec.limit),
            fees=types.fees.Fees.from_decoded(dec.fees),
            pool_apr=types.pool_apr.PoolApr.from_decoded(dec.pool_apr),
            max_request_execution_sec=dec.max_request_execution_sec,
            bump=dec.bump,
            lp_token_bump=dec.lp_token_bump,
            inception_time=dec.inception_time,
            parameter_update_oracle=types.secp256k1_pubkey.Secp256k1Pubkey.from_decoded(
                dec.parameter_update_oracle
            ),
            aum_usd_updated_at=dec.aum_usd_updated_at,
        )

    def to_json(self) -> PoolJSON:
        return {
            "name": self.name,
            "custodies": list(map(lambda item: str(item), self.custodies)),
            "aum_usd": self.aum_usd,
            "limit": self.limit.to_json(),
            "fees": self.fees.to_json(),
            "pool_apr": self.pool_apr.to_json(),
            "max_request_execution_sec": self.max_request_execution_sec,
            "bump": self.bump,
            "lp_token_bump": self.lp_token_bump,
            "inception_time": self.inception_time,
            "parameter_update_oracle": self.parameter_update_oracle.to_json(),
            "aum_usd_updated_at": self.aum_usd_updated_at,
        }

    @classmethod
    def from_json(cls, obj: PoolJSON) -> "Pool":
        return cls(
            name=obj["name"],
            custodies=list(
                map(lambda item: Pubkey.from_string(item), obj["custodies"])
            ),
            aum_usd=obj["aum_usd"],
            limit=types.limit.Limit.from_json(obj["limit"]),
            fees=types.fees.Fees.from_json(obj["fees"]),
            pool_apr=types.pool_apr.PoolApr.from_json(obj["pool_apr"]),
            max_request_execution_sec=obj["max_request_execution_sec"],
            bump=obj["bump"],
            lp_token_bump=obj["lp_token_bump"],
            inception_time=obj["inception_time"],
            parameter_update_oracle=types.secp256k1_pubkey.Secp256k1Pubkey.from_json(
                obj["parameter_update_oracle"]
            ),
            aum_usd_updated_at=obj["aum_usd_updated_at"],
        )
