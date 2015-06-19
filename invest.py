#!/usr/bin/env python

import sys
from datetime import datetime as dt
from operator import itemgetter
import logging
import json

import requests

AUTH_TOKEN = sys.argv[1]
HEADER = {'Authorization': AUTH_TOKEN}
INVESTOR_ID = sys.argv[2]
LOG_LOCATION = sys.argv[3]
VERSION = 'v1'

def get_balance():
    r = requests.get('https://api.lendingclub.com/api/investor/{}/accounts/{}/availablecash'.format(VERSION, INVESTOR_ID), headers=HEADER)
    if r.status_code == 200:
        return int(r.json()['availableCash'])
    else:
        raise Exception("Couldn't get balance. Status code {}".format(r.status_code))

def get_loans(numLoans):
    r = requests.get('https://api.lendingclub.com/api/investor/{}/loans/listing'.format(VERSION), headers=HEADER)
    loans = r.json()['loans']
    filtered_loans = filter_loans(loans, numLoans)
    return filtered_loans

def get_loans_owned():
    r = requests.get('https://api.lendingclub.com/api/investor/{}/accounts/{}/notes'.format(VERSION, INVESTOR_ID), headers = HEADER)
    return [x['loanId'] for x in r.json()['myNotes']]

def filter_loans(loans, num_loans):
    loans_owned = get_loans_owned()
    # This is where the action happens. Change this filter to
    # filter by different criteria.
    filtered = [x for x in loans if (
        x['id'] not in loans_owned and
        x['dti'] <= 20 and
        x['pubRec'] == 0 and
        x['purpose'] in ['debt_consolidation','renewable_energy',
            'wedding', 'credit_card'] and
        x['inqLast6Mths'] == 0 and
        x['homeOwnership'] in ['OWN','MORTGAGE'] and
        x['addrState'] not in ['CA','FL'] and
        (x['mthsSinceLastDelinq'] == None or
            x['mthsSinceLastDelinq'] <= 24)
        )]
    sorted_loans = sorted(filtered, key=itemgetter('intRate'))
    # return the num_loans loans with highest interest rate
    return [x['id'] for x in sorted_loans[-num_loans:]]


def make_loans(loans, amt_per_loan = 25):
    payload = {'aid':INVESTOR_ID, 'orders':
            [{'loanId':x, 'requestedAmount':amt_per_loan} for x in loans]}
    r = requests.post('https://api.lendingclub.com/api/investor/{}/accounts/{}/orders'.format(VERSION, INVESTOR_ID), json=payload, headers=HEADER)
    if r.status_code != 200:
        print(r.url)
        print(r.text)
        raise Exception("Couldn't complete order. Status code {}".format(r.status_code))
    response = r.json()
    order_id = response['orderInstructId']
    loans_made = len([x for x in response['orderConfirmations']
            if 'ORDER_FULFILLED' in x['executionStatus']])
    status = 'success' if loans_made else 'failure'
    return {'status': status, 'order_id':order_id, 'num_loans' : loans_made}



def main():
    with open(LOG_LOCATION, 'a') as o:
        o.write("{} User {}: Session started\n".format(dt.now().strftime("%d/%m/%Y %H:%M"),INVESTOR_ID))
        # Gets the balance
        moneyToInvest = get_balance()
        # If there's enough to buy a note, then do it
        if moneyToInvest > 25:
            numLoans = moneyToInvest // 25
            loans = get_loans(numLoans)
            if len(loans) > 0:
                orders = make_loans(loans)
                if orders['status'] == 'success':
                    o.write("Order Successful; Order ID: {}\n{} loan(s) added\n".format(orders['order_id'], orders['num_loans']))
                else:
                    o.write("Couldn't make loans. Perhaps they were funded?\n")
            else:
                o.write("No loans available\n")
        else:
            o.write("Only ${} in account - not enough money for loan\n".format(moneyToInvest))

if __name__ == '__main__':
    main()
