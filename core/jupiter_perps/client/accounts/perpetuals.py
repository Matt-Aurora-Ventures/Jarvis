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


class PerpetualsJSON(typing.TypedDict):
    permissions: types.permissions.PermissionsJSON
    pools: list[str]
    admin: str
    transfer_authority_bump: int
    perpetuals_bump: int
    inception_time: int


@dataclass
class Perpetuals:
    discriminator: typing.ClassVar = b"\x1c\xa7b\xbfhRl\xc4"
    layout: typing.ClassVar = borsh.CStruct(
        "permissions" / types.permissions.Permissions.layout,
        "pools" / borsh.Vec(typing.cast(Construct, BorshPubkey)),
        "admin" / BorshPubkey,
        "transfer_authority_bump" / borsh.U8,
        "perpetuals_bump" / borsh.U8,
        "inception_time" / borsh.I64,
    )
    permissions: types.permissions.Permissions
    pools: list[Pubkey]
    admin: Pubkey
    transfer_authority_bump: int
    perpetuals_bump: int
    inception_time: int

    @classmethod
    async def fetch(
        cls,
        conn: AsyncClient,
        address: Pubkey,
        commitment: typing.Optional[Commitment] = None,
        program_id: Pubkey = PROGRAM_ID,
    ) -> typing.Optional["Perpetuals"]:
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
    ) -> typing.List[typing.Optional["Perpetuals"]]:
        infos = await get_multiple_accounts(conn, addresses, commitment=commitment)
        res: typing.List[typing.Optional["Perpetuals"]] = []
        for info in infos:
            if info is None:
                res.append(None)
                continue
            if info.account.owner != program_id:
                raise ValueError("Account does not belong to this program")
            res.append(cls.decode(info.account.data))
        return res

    @classmethod
    def decode(cls, data: bytes) -> "Perpetuals":
        if data[:ACCOUNT_DISCRIMINATOR_SIZE] != cls.discriminator:
            raise AccountInvalidDiscriminator(
                "The discriminator for this account is invalid"
            )
        dec = Perpetuals.layout.parse(data[ACCOUNT_DISCRIMINATOR_SIZE:])
        return cls(
            permissions=types.permissions.Permissions.from_decoded(dec.permissions),
            pools=dec.pools,
            admin=dec.admin,
            transfer_authority_bump=dec.transfer_authority_bump,
            perpetuals_bump=dec.perpetuals_bump,
            inception_time=dec.inception_time,
        )

    def to_json(self) -> PerpetualsJSON:
        return {
            "permissions": self.permissions.to_json(),
            "pools": list(map(lambda item: str(item), self.pools)),
            "admin": str(self.admin),
            "transfer_authority_bump": self.transfer_authority_bump,
            "perpetuals_bump": self.perpetuals_bump,
            "inception_time": self.inception_time,
        }

    @classmethod
    def from_json(cls, obj: PerpetualsJSON) -> "Perpetuals":
        return cls(
            permissions=types.permissions.Permissions.from_json(obj["permissions"]),
            pools=list(map(lambda item: Pubkey.from_string(item), obj["pools"])),
            admin=Pubkey.from_string(obj["admin"]),
            transfer_authority_bump=obj["transfer_authority_bump"],
            perpetuals_bump=obj["perpetuals_bump"],
            inception_time=obj["inception_time"],
        )
