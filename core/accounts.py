from solders.pubkey import Pubkey
from spl.token.constants import TOKEN_PROGRAM_ID, ASSOCIATED_TOKEN_PROGRAM_ID

GRASS_PUBKEY = Pubkey.from_string("Grass7B4RdKfBCjTKgSqnXkqjwiGvQyFbuSCUJr3XXjs")
CLAIM_PUBKEY = Pubkey.from_string("Eohp5jrnGQgP74oD7ij9EuCSYnQDLLHgsuAmtSTuxABk")


def get_distributor_pda(version: int) -> Pubkey:

    pub, bump = Pubkey.find_program_address(
        seeds=[
            b"MerkleDistributor",
            GRASS_PUBKEY.__bytes__(),
            version.to_bytes(length=4, byteorder="little"),
        ],
        program_id=CLAIM_PUBKEY,
    )

    return pub


def get_claim_status_pda(owner: Pubkey, distributor: Pubkey) -> Pubkey:
    (pub, bump) = Pubkey.find_program_address(
        seeds=[b"ClaimStatus", owner.__bytes__(), distributor.__bytes__()],
        program_id=CLAIM_PUBKEY,
    )

    return pub


def get_token_pda(owner: Pubkey, mint: Pubkey) -> Pubkey:
    (pub, bump) = Pubkey.find_program_address(
        seeds=[owner.__bytes__(), TOKEN_PROGRAM_ID.__bytes__(), mint.__bytes__()],
        program_id=ASSOCIATED_TOKEN_PROGRAM_ID,
    )

    return pub
