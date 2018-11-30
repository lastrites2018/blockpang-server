from django.db import connections
from django.conf import settings
from django.shortcuts import render
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
import ast
import os
import urllib.request
import time

from iconsdk.wallet.wallet import KeyWallet
from iconsdk.signed_transaction import SignedTransaction
from iconsdk.icon_service import IconService
from iconsdk.providers.http_provider import HTTPProvider
from iconsdk.builder.call_builder import CallBuilder
from iconsdk.builder.transaction_builder import (
    TransactionBuilder,
    DeployTransactionBuilder,
    CallTransactionBuilder,
    MessageTransactionBuilder
)

cursor = connections['default'].cursor()
recipient = settings.RECIPIENT_LIST
default_score = settings.DEFAULT_SCORE_ADDRESS
icon_service = IconService(HTTPProvider(settings.ICON_SERVICE_PROVIDER))

keypath = os.path.join(os.path.dirname(__file__), 'iconkeystore2')
wallet = KeyWallet.load(keypath, "@icon222")
wallet_from = wallet.get_address()


def db_query(request, table):
    query = ['SELECT * FROM transaction;', 'SELECT * from users;']
    json_data = []

    if (table == 'transaction'):
        print('---querying transactionDB---')
        cursor.execute(query[0])
    elif (table == 'users'):
        print('---querying usersDB---')
        cursor.execute(query[1])
    
    row_headers = [x[0] for x in cursor.description]
    query_result = cursor.fetchall()
    for result in query_result:
        json_data.append(dict(zip(row_headers, result)))
        
    return HttpResponse(str(json_data))


def email(minlimit):
    subject = 'Icon Faucet: Not enough icx'
    message = f'Score has less than {minlimit} icx. Please add icx to score.'
    email_from = settings.EMAIL_HOST_USER
    send_mail(subject, message, email_from, recipient)
    print('email has been sent.')
    return HttpResponse('Email has been sent to admins.')


def update_admin(request, cmd, email):
    if cmd == 'add':
        recipient.append(email)
    elif cmd == 'delete':
        recipient.remove(email)
    return HttpResponse(str(recipient))


def transfer_stat(request):
    print('create transfer statistics',request)

    query = 'SELECT * FROM transaction;'
    cursor.execute(query)
    query_result = cursor.fetchall()


    return HttpResponse(str(query_result))


def user_stat(request):
    print('create users statistics',request)

    stat_result = {}

    # query = """
    # SELECT COUNT(wallet) FROM users
    # """

    query = """
    SELECT to_char(date_trunc('day', (current_date - offs)), 'YYYY-MM-DD')
    AS date 
    FROM generate_series(0, 365, 1) 
    AS offs
    """

    cursor.execute(query)
    stat_result['tatal_users'] = cursor.fetchall()

    return HttpResponse(str(stat_result))


def update_wallet(request):
    print('Update a wallet to database',request)
    insertDB_users(request,'request should includes wallet address')

    return 'success'

def create_wallet(request):
    print('Create a wallet',request)
    new_wallet = {}

    wallet = KeyWallet.create()
    # Check the wallet address
    new_wallet['address'] = wallet.get_address()
    # Let try getting the private key
    new_wallet['key'] = wallet.get_private_key()

    insertDB_users(request, new_wallet['address'])

    return str(new_wallet)


def insertDB_users(request, wallet):
    print('insertDB_users',request,wallet)
    req_body = ast.literal_eval(request.body.decode('utf-8'))

    try:
        req_body['wallet'] = req_body['wallet']
    except:
        req_body['wallet'] = wallet

    query = "INSERT INTO users (service_provider, wallet, email, user_pid) VALUES (%s,%s,%s,%s)"
    cursor.execute(query, (req_body['service_provider'],
                           req_body['wallet'], req_body['email'], req_body['user_pid']))
    connections['default'].commit()

    return 'USERS DB updated'


def get_limit():
    """ Get limits """
    call = CallBuilder().from_(wallet_from)\
        .to(default_score)\
        .method("get_limit")\
        .build()
    return icon_service.call(call)


def set_limit(request, amount_limit, block_limit):
    """Set a max amount and frequency of icx Score can send to user."""
    limit_setting = {}
    limit_setting['amount_limit'] = amount_limit
    limit_setting['block_limit'] = block_limit

    set_limit = CallTransactionBuilder()\
        .from_(wallet.get_address())\
        .to(default_score)\
        .step_limit(5000000)\
        .nid(3)\
        .nonce(100)\
        .method("set_limit")\
        .params({'amount_limit': amount_limit, 'block_limit': block_limit})\
        .build()

    # Returns the signed transaction object having a signature
    signed_transaction = SignedTransaction(set_limit, wallet)

    # Sends the transaction
    tx_hash = str(icon_service.send_transaction(signed_transaction))
    print('set_limit complete', tx_hash)  # added

    return str(limit_setting)


def get_block_balance():
    """Get a block's balance."""
    call = CallBuilder().from_(wallet_from)\
        .to(default_score)\
        .method("get_balance")\
        .build()

    return icon_service.call(call)


def get_wallet_balance(request, to_address):
    """Get a wallet balance."""
    call = CallBuilder().from_(wallet_from)\
        .to(default_score)\
        .method("get_to")\
        .params({'_from': wallet_from, '_to': to_address})\
        .build()
    return icon_service.call(call)


def send_transaction(request, to_address, value):
    """Send icx to a wallet."""
    print('transaction called')

    transaction = CallTransactionBuilder()\
        .from_(wallet.get_address())\
        .to(default_score)\
        .step_limit(5000000)\
        .nid(3)\
        .nonce(100)\
        .method("send_icx")\
        .params({'_to': to_address, 'value': value})\
        .build()

    # Returns the signed transaction object having a signature
    signed_transaction = SignedTransaction(transaction, wallet)
    print('transaction complete')

    # Sends the transaction
    return icon_service.send_transaction(signed_transaction)


def get_latest_transaction(request, to_address):
    """Get a wallet's latest transaction."""
    call = CallBuilder().from_(wallet_from)\
        .to(default_score)\
        .method("find_transaction")\
        .params({'_to': to_address})\
        .build()
    return icon_service.call(call)


def get_latest_block_height():
    """Get the latest block's height."""
    call = CallBuilder().from_(wallet_from)\
        .to(default_score)\
        .method("block_height")\
        .build()
    return icon_service.call(call)


def get_latest_block():
    """Get the latest block."""
    return icon_service.get_block('latest')


def get_transaction_result(tx_hash):
    # check the transaction result
    try:
        time.sleep(6)
        print('6s')
        tx_result = icon_service.get_transaction_result(tx_hash)
    except:
        time.sleep(6)
        print('12s')
        try:
            tx_result = icon_service.get_transaction_result(tx_hash)
        except:
            tx_result = {'failure': {
                'code': '0x7d65', 'message': "Please wait for few blocks to be created before requesting again"}}

    return tx_result
