# Celo Network Validator Exporter

Prometheus exporter that scrapes downtime and meta information for a specified validator signer address from the Celo blockchain. All data is collected from a blockchain node via RPC.

Supported Providers: http, ipc, websockets

## Motivation

There are multiple reasons why the Celo Network Validator Exporter is useful:

1. Running a validator on the Celo network requires close monitoring of its flawless operation meaning signing blocks and forming new blocks for the network. Geth already provides the possibility to expose Prometheus metrics enabling validator operators to monitor their nodes. However, if for any reason the Geth metric scraping will fail the operator is left with nothing than knowing the metrics cannot be scraped. For this reason a second independent way to get insights on the operation of the validator is desirable.
2. For infrastructure and failover automation based on metrics, false positives should be reduced to a minimum. The Celo Network Validator Exporter can help as one of multiple sources to verify/confirm a certain state of a validator.
3. Consecutive downtime blocks are not (yet) supported by the Geth metrics, hence, it is difficult to set a precise alert on those.

## Run From Source

Clone this repository and cd into the repository directory. Then run:

```
$ pip install --no-cache-dir -r requirements.txt
```

Set the necessary environment variables (see [Environment Variables](#environment-variables) for more):

```
$ export VALIDATOR_SIGNER_ADDRESS=<signer-address>
```

Run the exporter (make sure to run with Python 3):

```
$ python ./celo_web3_exporter
```

The exporter will use the default connection to the celo node RPC via `http://127.0.0.1:8545` and exposes the Prometheus metrics at `http://localhost:8000/metrics`.

## Run with Docker

### Docker Hub
Pull the image:
```
$ docker pull virtualhive/celo-network-validator-exporter
```

Run the exporter (make sure to replace `<signer-address>` and the connection string):
```
$ docker run -d --name celo-network-validator-exporter \
-e VALIDATOR_SIGNER_ADDRESS=<signer-address> \
-e CONNECTION_STRING=http://127.0.0.1:8545 \
-p 8000:8000 virtualhive/celo-network-validator-exporter
```

### Build Image From Source

Sample image build command:

```
$ docker build -t celo-network-validator-exporter_local .
```

Sample run command (make sure to replace `<signer-address>` and the connection string):

```
$ docker run -d --name celo_web3_exporter \
-e VALIDATOR_SIGNER_ADDRESS=<signer-address> \
-e CONNECTION_STRING=http://127.0.0.1:8545 \
-p 8000:8000 celo-network-validator-exporter_local
```

## Environment Variables

Variable | Description | Default
-------- | ----------- | -------
VALIDATOR_SIGNER_ADDRESS | signer address of the validator to monitor | none
PROMETHEUS_PORT | metrics exposing port | 8000
CONNECTION_PROVIDER | RPC protocol, one of 'http', 'rpc', 'ws' | http
CONNECTION_STRING | RPC connection string to the node<br>Examples:<br>http://127.0.0.1:8545<br>file:///path/to/node/rpc-json/file.ipc<br>ws://127.0.0.1:8546 | http://127.0.0.1:8545

Notice: rpc (IPC socket) and ws (websocket) providers are *not* tested!

## Metrics

| Metric                                      | Type    | Description                                                  |
| ------------------------------------------- | ------- | ------------------------------------------------------------ |
| celochain_downtime_blocks_total             | Counter | Cumulative total of downtime blocks since the exporter was started |
| celochain_downtime_blocks_consecutive       | Gauge   | Current consecutive downtime blocks (resets immediately when a block was signed after consecutive downtime blocks) |
| celochain_downtime_blocks_consecutive_slow* | Gauge   | Consecutive downtime blocks with a slow reset (resets after 3 signed blocks after the last consecutive downtime block was detected) |
| celochain_latest_block_number               | Gauge   | Latest block number                                          |
| celochain_epoch_current                     | Gauge   | Current epoch number                                         |
| celochain_epoch_countdown_blocks            | Gauge   | Blocks remaining until epoch change                          |
| celochain_epoch_countdown_seconds           | Gauge   | Seconds remaining until epoch change                         |
| celochain_web3_client_info                  | Info    | labels: signer, celo node version info                       |
| celochain_exporter_info                     | Info    | labels: exporter version                                     |

*The *celochain_downtime_blocks_consecutive_slow* metric was introduced to cope with possibly missed or delayed scrapes by Prometheus. Since the consecutive downtime blocks is a very important metric to monitor a validator on, the slow reset allows for a more robust setup and gives more time to scrape the maximum of consecutive downtime blocks.

### Example

```python
# HELP celochain_downtime_blocks_total Cumulative downtime block counter
# TYPE celochain_downtime_blocks_total counter
celochain_downtime_blocks_total{signer="0x123456789AbCdEf"} 3.0
# HELP celochain_downtime_blocks_consecutive Current consecutive downtime blocks
# TYPE celochain_downtime_blocks_consecutive gauge
celochain_downtime_blocks_consecutive{signer="0x123456789AbCdEf"} 0.0
# HELP celochain_downtime_blocks_consecutive_slow Slow resetting consecutive downtime blocks
# TYPE celochain_downtime_blocks_consecutive_slow gauge
celochain_downtime_blocks_consecutive_slow{signer="0x123456789AbCdEf"} 0.0
# HELP celochain_latest_block_number Latest block queried from the blockchain
# TYPE celochain_latest_block_number gauge
celochain_latest_block_number 2.629694e+06
# HELP celochain_epoch_current Current epoch number
# TYPE celochain_epoch_current gauge
celochain_epoch_current 153.0
# HELP celochain_epoch_countdown_blocks Blocks remaining until epoch change
# TYPE celochain_epoch_countdown_blocks gauge
celochain_epoch_countdown_blocks 14147.0
# HELP celochain_epoch_countdown_seconds Seconds remaining until epoch change
# TYPE celochain_epoch_countdown_seconds gauge
celochain_epoch_countdown_seconds 70735.0
# HELP celochain_web3_client_info Web3 connected node information
# TYPE celochain_web3_client_info gauge
celochain_web3_client_info{signer="0x123456789AbCdEf",version="celo/v1.0.1-stable/linux-amd64/go1.13.14"} 1.0
# HELP celochain_exporter_info Exporter information
# TYPE celochain_exporter_info gauge
celochain_exporter_info{up_since="1600722537.4102187",version="1.0.0"} 1.0
```

## Prometheus Configuration

The scrape interval should be at 5s to get all information in time.

Example job config:

```
  - job_name: celo_network_validator_exporter
    scrape_interval: 5s
    metrics_path: /metrics
    static_configs:
      - targets: ['172.17.0.5:8000', '172.17.0.6:8000']
```



## Grafana Dashboard

- todo