from borsh_construct import CStruct, U8, U64, I64
from dataclasses import dataclass

from solders.pubkey import Pubkey


ClaimStatusSchema = CStruct(
    "claimant" / U8[32],
    "allocation" / U64,
    "sent_allocation" / U64,
    "claimed_ts" / I64,
)


@dataclass
class ClaimStatus:
    claimant: Pubkey
    allocation: int
    sent_allocation: int
    claimed_ts: int

    @staticmethod
    def deserialize(data: bytes) -> "ClaimStatus":
        parsed_data = ClaimStatusSchema.parse(data)

        return ClaimStatus(
            claimant=Pubkey.from_bytes(bytes(parsed_data.claimant)),
            allocation=parsed_data.allocation,
            sent_allocation=parsed_data.sent_allocation,
            claimed_ts=parsed_data.claimed_ts,
        )


