import json
import traceback
from hashlib import sha256
from math import floor

import spl.token.instructions
from borsh_construct import U8, U64, CStruct, Vec
from solana.constants import SYSTEM_PROGRAM_ID
from solana.rpc.async_api import AsyncClient
from solana.rpc.commitment import Finalized, Processed
from solana.rpc.types import TxOpts
from solana.transaction import Transaction
from solders.instruction import AccountMeta, Instruction
from solders.keypair import Keypair
from solders.pubkey import Pubkey
from spl.token.constants import TOKEN_PROGRAM_ID
from spl.token.instructions import TransferParams, create_associated_token_account

from data.config import DESTINATION_ADDRESS, RPC_URL, TIP_AMOUNT
from utils import logger

from .accounts import (
    CLAIM_PUBKEY,
    GRASS_PUBKEY,
    get_claim_status_pda,
    get_distributor_pda,
    get_token_pda,
)
from .schema import ClaimStatus

INSTRUCTION_NAMESPACE = "global"
INSTRUCTION_NAME = "claim"


HashArray = U8[32]
ClaimInputSchema = CStruct("allocation" / U64, "proof" / Vec(HashArray))

def to_fixed(n: str | float, d: int = 0) -> str:
    d = int('1' + ('0' * d))
    result = str(floor(float(n) * d) / d)
    if result.endswith(".0"):
        result = result[:-2]
    return result

def get_function_hash(instruction_namespace: str, instruction_name: str):
    preimage = f"{instruction_namespace}:{instruction_name}".encode("utf-8")
    sighash = sha256(preimage).digest()
    return sighash[:8]


def get_data(allocation: int, proof: list[bytes]):
    function_hash = get_function_hash(INSTRUCTION_NAMESPACE, INSTRUCTION_NAME)

    data_struct = {"allocation": allocation, "proof": proof}

    serialized_data = ClaimInputSchema.build(data_struct)

    return function_hash + serialized_data


def get_claim_ix(
    distributor: Pubkey,
    claim_status: Pubkey,
    _from: Pubkey,
    to: Pubkey,
    claimant: Pubkey,
    allocation: int,
    proof: list[bytes],
) -> Instruction:
    data = get_data(allocation, proof)

    accounts = [
        AccountMeta(pubkey=distributor, is_signer=False, is_writable=True),
        AccountMeta(pubkey=GRASS_PUBKEY, is_signer=False, is_writable=False),
        AccountMeta(pubkey=claim_status, is_signer=False, is_writable=True),
        AccountMeta(pubkey=_from, is_signer=False, is_writable=True),
        AccountMeta(pubkey=to, is_signer=False, is_writable=True),
        AccountMeta(pubkey=claimant, is_signer=True, is_writable=True),
        AccountMeta(pubkey=TOKEN_PROGRAM_ID, is_signer=False, is_writable=False),
        AccountMeta(pubkey=SYSTEM_PROGRAM_ID, is_signer=False, is_writable=False),
    ]

    instruction = Instruction(program_id=CLAIM_PUBKEY, data=data, accounts=accounts)

    return instruction

async def transferer(private_key: str, dest_address: str) -> None:
    dest_pubkey = Pubkey.from_string(s=dest_address)
    provider = AsyncClient(endpoint=RPC_URL, commitment=Processed)

    keypair = Keypair.from_base58_string(s=private_key)

    ata = get_token_pda(owner=keypair.pubkey(), mint=GRASS_PUBKEY)
    balance_resp = await provider.get_token_account_balance(pubkey=ata, commitment=Finalized)

    balance = int(balance_resp.value.amount)

    ixs = []

    dest_ata = get_token_pda(owner=dest_pubkey, mint=GRASS_PUBKEY)
    dest_ata_info = await provider.get_account_info(pubkey=dest_ata)

    if dest_ata_info.value is None:
        create_dest_ix = spl.token.instructions.create_associated_token_account(
            payer=keypair.pubkey(), owner=dest_pubkey, mint=GRASS_PUBKEY
        )

        ixs.append(create_dest_ix)

    transfer_ix = spl.token.instructions.transfer(
        TransferParams(
            program_id=TOKEN_PROGRAM_ID,
            source=ata,
            dest=dest_ata,
            owner=keypair.pubkey(),
            amount=balance,
            signers=[keypair.pubkey()],
        )
    )

    ixs.append(transfer_ix)

    recent_block_hash_resp = await provider.get_latest_blockhash(commitment=Finalized)
    recent_block_hash = recent_block_hash_resp.value.blockhash

    tx = Transaction(recent_blockhash=recent_block_hash, fee_payer=keypair.pubkey(), instructions=ixs).to_solders()

    signers = [keypair]
    tx.sign(signers, recent_blockhash=recent_block_hash)

    signature_resp = await provider.send_transaction(
        txn=tx,
        opts=TxOpts(
            skip_confirmation=False,
        ),
    )

    signature = signature_resp.value

    logger.info(f"https://solscan.io/tx/{signature}")


async def claimer(private_key: str, version: int, claim_proof: str, allocation: int) -> bool:
    i = 0

    while i < 10:
        try:
            i += 1

            rpc_url = RPC_URL

            provider = AsyncClient(endpoint=rpc_url, commitment=Processed)

            provider._provider.logger = logger

            keypair = Keypair.from_base58_string(s=private_key)

            logger.info("Start claiming: ", keypair.pubkey())

            dest_pubkey = Pubkey.from_string(s=DESTINATION_ADDRESS)

            distributor = get_distributor_pda(version=version)

            claim_status_pubkey = get_claim_status_pda(owner=keypair.pubkey(), distributor=distributor)

            claim_status_response = await provider.get_account_info(pubkey=claim_status_pubkey, commitment=Finalized)

            if claim_status_response.value is not None:
                claim_status_data = claim_status_response.value.data
                claim_status = ClaimStatus.deserialize(claim_status_data[8:])

                if claim_status.allocation == claim_status.sent_allocation:
                    logger.info("Already claimed")
                    return True

            token_vault = get_token_pda(owner=distributor, mint=GRASS_PUBKEY)

            token_ata = get_token_pda(owner=keypair.pubkey(), mint=GRASS_PUBKEY)

            ixs = []

            create_token_ix = create_associated_token_account(
                payer=keypair.pubkey(), owner=keypair.pubkey(), mint=GRASS_PUBKEY
            )

            ixs.append(create_token_ix)

            parsed = json.loads(claim_proof)

            proof = [bytes(e["data"]["data"]) for e in parsed]

            claim_ix = get_claim_ix(
                distributor=distributor,
                claim_status=claim_status_pubkey,
                _from=token_vault,
                to=token_ata,
                claimant=keypair.pubkey(),
                allocation=allocation,
                proof=proof,
            )

            ixs.append(claim_ix)

            dest_ata = get_token_pda(owner=dest_pubkey, mint=GRASS_PUBKEY)

            dest_info = await provider.get_account_info(pubkey=dest_ata)

            if dest_info.value is None:
                create_dest_ix = spl.token.instructions.create_associated_token_account(
                    payer=keypair.pubkey(), owner=dest_pubkey, mint=GRASS_PUBKEY
                )

                ixs.append(create_dest_ix) 

            amount_to_withdraw = allocation

            transfer_ix = spl.token.instructions.transfer(
                TransferParams(
                    program_id=TOKEN_PROGRAM_ID,
                    source=token_ata,
                    dest=dest_ata,
                    owner=keypair.pubkey(),
                    amount=int(amount_to_withdraw),
                    signers=[keypair.pubkey()],
                )
            )
            ixs.append(transfer_ix)
            
            recent_block_hash_resp = await provider.get_latest_blockhash(commitment=Finalized)
            recent_block_hash = recent_block_hash_resp.value.blockhash

            tx = Transaction(recent_blockhash=recent_block_hash, fee_payer=keypair.pubkey(), instructions=ixs).to_solders()

            signers = [keypair]
            tx.sign(signers, recent_blockhash=recent_block_hash)

            signature_resp = await provider.send_transaction(
                txn=tx,
                opts=TxOpts(
                    skip_confirmation=False,
                ),
            )

            signature = signature_resp.value

            logger.info(f"https://solscan.io/tx/{signature}")

            return True
        except Exception as e:
            logger.warning(f"Error in claim: {str(e)} | Continue..")
            return False
