import argparse
import subprocess
import time
import json
import requests

# Parameters
base = 50
interval = 10
max_cpu = 150
period  = 60
namespace = "lab23"
pod_name = "open5gs-upf-59fd7664f-r4s4z"
container_name = "open5gs-upf"
prometheus_url = "http://192.168.13.3:9090/api/v1/query"
query = 'amf_session{service="open5gs-amf-metrics",namespace="lab23"}'


def parse_args():
    '''
    Parses command-line arguments for configuring the QoS SDN Controller.

    Returns:
        argparse.Namespace: Object containing all parsed arguments:
            --base (int): Base CPU in millicores (default: 100)
            --interval (int): CPU increment per UE session in millicores (default: 15)
            --max (int): Maximum CPU allocation in millicores (default: 1600)
            --period (int): Interval in seconds between control loop iterations (default: 10)
            --pod_name (str): Name of the Kubernetes pod to scale (default: 'upf-0')
            --namespace (str): Kubernetes namespace where the pod resides (default: 'open5gs')
    '''
    parser = argparse.ArgumentParser(description='QoS SDN Controller for UPF scaling')
    parser.add_argument('--base', type=int, default=base, help='Base CPU in millicores')
    parser.add_argument('--interval', type=int, default=interval, help='CPU increment per UE session in millicores')
    parser.add_argument('--max', type=int, default=max_cpu, help='Max CPU in millicores')
    parser.add_argument('--period', type=int, default=period, help='Polling period in seconds')
    parser.add_argument('--pod_name', type=str, default=pod_name, help='Target pod name')
    parser.add_argument('--namespace', type=str, default=namespace, help='Kubernetes namespace')
    return parser.parse_args()


def get_ue_sessions():
  response = requests.get(prometheus_url, params={'query': query})
  if response.status_code == 200:
      try:
          result = response.json()
          amf_sessions = result['data']['result'][0]['value'][1]
          print(f"======================AMF sessions: {amf_sessions}=====================================")
          return amf_sessions
      except (IndexError, KeyError):
          print("No data in request.")
          return -1
  else:
      print(f"Failed. Code: {response.status_code}")
      return -1

    
def patch_pod_resources(base, interval, max_cpu, count, container_name, pod_name, namespace):
  new_cpu = min(base + interval * int(count), max_cpu)
  new_cpu = str(new_cpu)+"m"
  
  print(f"******************Base: {base} New cpu: {new_cpu}*********************************")
  # Budowa komendy
  kubectl_cmd = [
      "kubectl", "patch", "-n", namespace,
      "pod", pod_name,
      "--subresource", "resize",
      "--patch", f'{{"spec":{{"containers":[{{"name":"{container_name}", "resources":{{"requests":{{"cpu":"{new_cpu}"}}}}}}]}}}}'
  ]
  
  # Wykonanie komendy
  result = subprocess.run(kubectl_cmd, capture_output=True, text=True)
  
  # Sprawdzenie wyniku
  if result.returncode == 0:
      print("Patch applied successfully.")
      print(result.stdout)
  else:
      print("Error applying patch:")
      print(result.stderr)
      
      
      
def main():
    '''
        Main control loop for the QoS SDN Controller.

        Continuously monitors the number of active UE sessions via Prometheus,
        calculates the required CPU allocation based on a linear policy, and
        updates the resource allocation of a specified Kubernetes pod accordingly.

        Steps:
            1. Parses command-line arguments defining scaling policy and targets.
            2. Periodically queries Prometheus for the 'amf_sessions' metric.
            3. Computes new CPU resource values using the scaling formula.
            4. Applies the updated CPU configuration to the target pod using `kubectl`.

        The loop repeats every 'period' seconds as specified in the arguments.
        '''
    args = parse_args()
    print("Starting control loop...")

    while True:
        count_ue = get_ue_sessions()
        if count_ue is not None:
            patch_pod_resources(base=args.base, interval=args.interval, max_cpu=args.max,
                                count=count_ue, container_name=container_name, pod_name=args.pod_name,
                                namespace=args.namespace)
        time.sleep(args.period)


if __name__ == "__main__":
    main()
      
      

