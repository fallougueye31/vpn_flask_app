import os
from time import sleep

from flask import Flask, jsonify, render_template
from datetime import datetime, timedelta, timezone
import boto3
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

# AWS Client VPN Endpoint ID (Replace with your actual VPN endpoint ID)
VPN_ENDPOINT_ID = os.getenv("VPN_ENDPOINT_ID")
AWS_REGION = "eu-central-1"

# Initialize Boto3 client
client = boto3.client("ec2", region_name=AWS_REGION)
cloudwatch = boto3.client('cloudwatch', region_name=AWS_REGION)
client_logs = boto3.client("logs", region_name=AWS_REGION)


def get_connected_clients():
    try:
        response = client.describe_client_vpn_connections(ClientVpnEndpointId=VPN_ENDPOINT_ID)
        connections = response.get("Connections", [])
        connected_clients = [
            {
                "username": conn.get("CommonName", "Unknown"),
                "connection_id": conn.get("ConnectionId"),
                "status": conn.get("Status", {}).get("Code"),
                "ip": conn.get("ClientIp"),
                "timestamp": conn.get("ConnectionEstablishedTime"),
                "ingress_data": conn.get("IngressBytes"),
                "egress_data": conn.get("EgressBytes"),
                "end_time" : conn.get("ConnectionEndTime")
            }
            for conn in connections if conn.get("Status", {}).get("Code") == "active"
        ]
        return connected_clients
    except Exception as e:
        print(f"Error fetching VPN connections: {e}")
        return []


def get_others_clients():
    # Configuration
    log_group = "/aws/vpn-tgu-prod/vpn_tgur"  # <-- Replace with your actual log group
    query_string = """
    fields @timestamp, @message, 'Terminated' as status1
    | parse @message /"connection-id":\s*"(?<connectionId>[^"]+)"/
    | parse @message /"client-ip":\s*"(?<clientIp>[^"]+)"/
    | parse @message /"common-name":\s*"(?<commonName>[^"]+)"/
    | parse @message /"connection-start-time":\s*"(?<startTime>[^"]+)"/
    | parse @message /"connection-end-time":\s*"(?<endTime>[^"]*)"/
    | parse @message /"connection-log-type":\s*"(?<logtype>[^"]+)"/
    | parse @message /"ingress-bytes":\s*"(?<ingressbytes>[^"]+)"/
    | parse @message /"egress-bytes":\s*"(?<egressbytes>[^"]+)"/
    | filter clientIp != "NA" and endTime != "NA"
    | stats  latest(startTime) as timestamp,
             latest(endTime) as end_time,
             latest(commonName) as username,
             latest(clientIp) as ip,
             latest(connectionId) as connection_id,
             latest(egressbytes) as egress_data,
             latest(ingressbytes) as ingress_data,
             latest(status1) as status
      by connectionId
    | sort timestamp desc
    """

    # Time range: last 15 days
    end_time = datetime.now(timezone.utc)
    start_time = end_time - timedelta(days=15)

    # Initialize CloudWatch Logs client

    # Start query
    response = client_logs.start_query(
        logGroupName=log_group,
        startTime=int(start_time.timestamp()),
        endTime=int(end_time.timestamp()),
        queryString=query_string,
    )

    query_id = response["queryId"]

    # Wait for query to complete
    print("Running query...")
    try:
        while True:
            result = client_logs.get_query_results(queryId=query_id)
            if result["status"] == "Complete":
                break
            sleep(2)

        print(len(result["results"]))
        # Print results
        results_parse = []
        for row in result["results"]:
            log = {field["field"]: field["value"] for field in row}
            results_parse.append(log)
        return results_parse

    except Exception as e:
            print(f"Error fetching VPN others connections: {e}")
            return []


def get_all_clients():
    return get_connected_clients() + get_others_clients()


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/clients")
def api_clients():
    return jsonify(get_all_clients())


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
