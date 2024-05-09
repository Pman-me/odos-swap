import json
import os
import random

from web3 import Web3
import requests

import wallet_addresses
from arbitrum import consts

w3 = Web3(Web3.HTTPProvider("https://arb1.arbitrum.io/rpc"))

quote_url = "https://api.odos.xyz/sor/quote/v2"

assemble_url = "https://api.odos.xyz/sor/assemble"

chain_id = consts.chain_id
target_chain_dir = './arbitrum'

file_ls = [file for file in os.listdir(target_chain_dir) if file.endswith('.json')]


for pb, pk in zip(wallet_addresses.wallet_address_ls, wallet_addresses.pk_ls):

    user_addr = Web3.to_checksum_address(pb)

    while True:
        r = random.randint(0, len(file_ls) - 1)
        input_abi_dir = file_ls[r]
        input_symbol_name = input_abi_dir.split('_')[0]

        input_token_address = Web3.to_checksum_address(consts.mapping_symbol_contract_address.get(input_symbol_name))

        with open(target_chain_dir + '/' + input_abi_dir) as abi_file:
            input_token_contract_abi = json.load(abi_file)

        input_token_contract = w3.eth.contract(address=input_token_address,abi=input_token_contract_abi)
        input_token_balance = input_token_contract.functions.balanceOf(user_addr).call()

        if input_token_balance > 0:
            break

    if r == len(file_ls) - 1:
        output_abi_dir = file_ls[r - 1]
    else:
        output_abi_dir = file_ls[r + 1]

    output_symbol_name = output_abi_dir.split('_')[0]

    output_token_address = Web3.to_checksum_address(consts.mapping_symbol_contract_address.get(output_symbol_name))

    quote_request_body = {
        "chainId": chain_id,
        "inputTokens": [
            {
                "tokenAddress": input_token_address,
                "amount": str(input_token_balance),
            }
        ],
        "outputTokens": [
            {
                "tokenAddress": output_token_address,
                "proportion": 1
            }
        ],
        "slippageLimitPercent": 0.3,
        "userAddr": user_addr,
        "referralCode": 0,
        "disableRFQs": True,
        "compact": True,
    }

    response = requests.post(
        quote_url,
        headers={"Content-Type": "application/json"},
        json=quote_request_body
    )

    if response.status_code == 200:
        quote = response.json()

        assemble_request_body = {
            "userAddr": user_addr,
            "pathId": quote["pathId"],
            "simulate": False,
            # this can be set to true if the user isn't doing their own estimate gas call for the transaction
        }

        response = requests.post(
            assemble_url,
            headers={"Content-Type": "application/json"},
            json=assemble_request_body
        )

        if response.status_code == 200:
            assembled_transaction = response.json()

            # approve
            #################################################################
            spender_address = assembled_transaction['transaction']['to']

            nonce = w3.eth.get_transaction_count(user_addr)

            approve_tx_param = assembled_transaction['transaction'].copy()
            approve_tx_param.pop('data', None)
            approve_tx_param.pop('to', None)
            approve_tx_param.pop('value', None)

            approve_transaction = input_token_contract.functions.approve(spender_address, input_token_balance).build_transaction(
                approve_tx_param
            )

            signed_approve_tx = w3.eth.account.sign_transaction(approve_transaction, pk)

            approve_tx_hash = w3.eth.send_raw_transaction(signed_approve_tx.rawTransaction)
            approve_receipt = w3.eth.wait_for_transaction_receipt(approve_tx_hash, timeout=60)

            # swap
            ####################################################################
            transaction = assembled_transaction["transaction"]
            transaction['nonce'] = w3.eth.get_transaction_count(user_addr)

            transaction["value"] = int(transaction["value"])
            signed_tx = w3.eth.account.sign_transaction(transaction, pk)

            tx_hash = w3.eth.send_raw_transaction(signed_tx.rawTransaction)
            receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)
            print(f'tx hash for wallet address {user_addr}: ', tx_hash.hex(), flush=True)

        else:
            print(f"Error in Transaction Assembly: {response.json()}", flush=True)
            # handle Transaction Assembly failure cases

    else:
        print(f"Error in Quote for wallet address {user_addr}: {response.json()}", flush=True)

    print('################################################')




