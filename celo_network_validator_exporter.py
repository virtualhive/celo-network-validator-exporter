#!/usr/bin/python3

from _version import __version__
import os
import time
import logging
from web3 import Web3
from prometheus_client import Counter, Gauge, Info, start_http_server
import virtual_hive
from celo_exporter import CeloWeb3

virtual_hive.vh_common.print_welcome()

# initial setup
logging.basicConfig(format='%(asctime)s %(levelname)s: %(message)s',level=logging.INFO)
default_prometheus_port = 8000
prometheus_port = int(os.getenv('PROMETHEUS_PORT', default_prometheus_port))
celo_web3 = CeloWeb3()

# setup prometheus metrics
prometheus_downtime_blocks_counter = Counter('celochain_downtime_blocks', 'Cumulative downtime block counter', ['signer'])
prometheus_downtime_blocks_consecutive_gauge = Gauge('celochain_downtime_blocks_consecutive', 'Current consecutive downtime blocks', ['signer'])
prometheus_downtime_blocks_consecutive_slow_gauge = Gauge('celochain_downtime_blocks_consecutive_slow', 'Slow resetting consecutive downtime blocks', ['signer'])
prometheus_latest_block_number = Gauge('celochain_latest_block_number', 'Latest block queried from the blockchain', ['signer'])
prometheus_epoch_current_gauge = Gauge('celochain_epoch_current', 'Current epoch number', ['signer'])
prometheus_epoch_countdown_blocks_gauge = Gauge('celochain_epoch_countdown_blocks', 'Blocks remaining until epoch change', ['signer'])
prometheus_epoch_countdown_seconds_gauge = Gauge('celochain_epoch_countdown_seconds', 'Seconds remaining until epoch change', ['signer'])
prometheus_web3_client_info = Info('celochain_web3_client', 'Web3 connected node information', ['signer'])
prometheus_exporter_info = Info('celochain_exporter', 'Exporter information', ['signer'])

# start prometheus server
logging.info('Starting prometheus server on port %i...' % prometheus_port)
start_http_server(prometheus_port)

# read validator signer address
default_signer_address = 'none'
signer_address = os.getenv('VALIDATOR_SIGNER_ADDRESS', default_signer_address)
if signer_address == 'none':
    logging.error('Signer address not set! Check the environment variable VALIDATOR_SIGNER_ADDRESS')
    exit(1)
logging.info('Signer address: %s' % signer_address)

# connection setup
w3 = celo_web3.get_web3_connection()

# initialize metrics
prometheus_exporter_info.labels(signer_address).info({'version': __version__})
prometheus_downtime_blocks_consecutive_gauge.labels(signer_address).set(0)
prometheus_downtime_blocks_consecutive_slow_gauge.labels(signer_address).set(0)
prometheus_latest_block_number.labels(signer_address).set(0)
prometheus_web3_client_info.labels(signer_address).info({'version': w3.clientVersion})

logging.info('Client version: %s' % w3.clientVersion)


# initialization
consecutive_blocks = 0
consecutive_blocks_slow_reset = 0
slow_reset_delay = 3 # keep the consecutive_blocks_slow_reset for 3 more blocks before reset
slow_reset_counter = 0
last_downtime_block_number = 0
last_block_number = 0
downtime_counter = 0
reset_delay = 3
is_epoch_change = False
(_, epoch_current, epoch_end_block_number) = celo_web3.get_epoch_info()
prometheus_epoch_current_gauge.labels(signer_address).set(epoch_current)
signer_address_index = celo_web3.get_validator_id(signer_address)

logging.info('Listening...')

# main loop
while True:
    latest_block = celo_web3.get_latest_block()
    latest_block_number = latest_block['number']
    prometheus_latest_block_number.labels(signer_address).set(latest_block_number)

    # check if it's a new block
    if latest_block_number != last_block_number:
        logging.debug('New block: #%s' % latest_block_number)

        # set prometheus epoch countdown metrics
        prometheus_epoch_countdown_blocks_gauge.labels(signer_address).set(epoch_end_block_number - last_block_number)
        prometheus_epoch_countdown_seconds_gauge.labels(signer_address).set((epoch_end_block_number - last_block_number) * 5)

        # check if there's a new epoch
        if is_epoch_change:
            (_, epoch_current, epoch_end_block_number) = celo_web3.get_epoch_info()

            # set prometheus epoch metrics
            prometheus_epoch_current_gauge.labels(signer_address).set(epoch_current)
            prometheus_epoch_countdown_blocks_gauge.labels(signer_address).set(epoch_end_block_number - last_block_number)
            prometheus_epoch_countdown_seconds_gauge.labels(signer_address).set((epoch_end_block_number - last_block_number) * 5)

            # get (possibly new) signer address ID from the (possibly new) validator set
            signer_address_index = celo_web3.get_validator_id(signer_address)
            is_epoch_change = False

        # get bitmap and signer bit for the signer ID of interest
        bitmap = celo_web3.decode_signing_bitmap(latest_block)
        signer_bit = celo_web3.get_signer_bit(latest_block, signer_address_index)

        # signer address didn't sign
        if signer_bit == '0':
            downtime_counter = downtime_counter + 1
            prometheus_downtime_blocks_counter.labels(signer_address).inc()
            logging.warning('Downtime at block: #%i' % latest_block_number)
            logging.warning('Decoded bitmap: %s' % bitmap)
            logging.warning('ID marker:      ' + (' ' * signer_address_index) + '^')

            # previous block was also not signed by us
            if latest_block_number == (last_downtime_block_number + 1):
                consecutive_blocks = consecutive_blocks + 1
                consecutive_blocks_slow_reset = consecutive_blocks_slow_reset + 1
                prometheus_downtime_blocks_consecutive_gauge.labels(signer_address).set(consecutive_blocks)
                prometheus_downtime_blocks_consecutive_slow_gauge.labels(signer_address).set(consecutive_blocks_slow_reset)

            # previous block was signed by us
            else:
                consecutive_blocks = 1
                consecutive_blocks_slow_reset = 1
                slow_reset_counter = 0
                prometheus_downtime_blocks_consecutive_gauge.labels(signer_address).set(consecutive_blocks)
                prometheus_downtime_blocks_consecutive_slow_gauge.labels(signer_address).set(consecutive_blocks_slow_reset)
            logging.warning('Consecutive downtime blocks: %i' % consecutive_blocks)
            last_downtime_block_number = latest_block_number
            logging.warning('Downtime total: %i' % downtime_counter)

        # signer address did sign
        elif signer_bit == '1':
            logging.debug('Validator signature found in the block!')

            # reset the consecutive block gauge if there was downtime before
            if consecutive_blocks > 0:
                logging.info('Reset consecutive block gauge')
                consecutive_blocks = 0
                prometheus_downtime_blocks_consecutive_gauge.labels(signer_address).set(consecutive_blocks)
            if consecutive_blocks_slow_reset > 0:
                if slow_reset_counter < slow_reset_delay:
                    slow_reset_counter = slow_reset_counter + 1
                else:
                    consecutive_blocks_slow_reset = 0
                    slow_reset_counter = 0
                    prometheus_downtime_blocks_consecutive_slow_gauge.labels(signer_address).set(consecutive_blocks_slow_reset)
                    logging.info('Reset slow consecutive block gauge')

        # something is off
        else:
            logging.error('Signer bit invalid! Signer bit: "%s"' % signer_bit)

            # not really epoch change but make sure to get fresh info for the next run
            is_epoch_change = True
        
        last_block_number = latest_block_number

        # epoch change check
        if (latest_block_number == epoch_end_block_number):
            logging.info('Last block of epoch reached!')
            is_epoch_change = True

    # throttle requests
    time.sleep(1)
