
from flask import Flask, jsonify, render_template
from datetime import datetime, timedelta
import boto3

app = Flask(__name__)

# AWS Client VPN Endpoint ID (Replace with your actual VPN endpoint ID)
VPN_ENDPOINT_ID = "cvpn-endpoint-00701398d9c3b7ce7"
AWS_REGION = "eu-central-1"

# Initialize Boto3 client
client = boto3.client("ec2", region_name=AWS_REGION)
cloudwatch = boto3.client('cloudwatch', region_name=AWS_REGION)


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
                "egress_data" :conn.get("EgressBytes")
            }
            for conn in connections if conn.get("Status", {}).get("Code") == "active"
        ]
        return connected_clients
    except Exception as e:
        print(f"Error fetching VPN connections: {e}")
        return []

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/clients")
def api_clients():
    return jsonify(get_connected_clients())


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
