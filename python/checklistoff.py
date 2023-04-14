from googleapiclient import discovery
from oauth2client.client import GoogleCredentials
import time
import configparser
import ipaddress
from google.cloud import compute_v1 
# from collections import defaultdict
# Reading properties file
config = configparser.ConfigParser()
config.read('check-list-prj.properties')
# Uncomment to use Application Default Credentials (ADC)
credentials = GoogleCredentials.get_application_default()
cloudresourcemanager = discovery.build('cloudresourcemanager', 'v1', credentials=credentials)
compute = discovery.build('compute', 'v1', credentials=credentials)
container = discovery.build('container', 'v1', credentials=credentials)
instance_client = compute_v1.InstancesClient()

class Colors:

  HEADER = '\033[32m'# $95
  OKBLUE = '\033[90m'
  OKCYAN = '\033[90m'
  OKGREEN = '\033[92m'
  WARNING = '\033[93m'
  FAIL = '\033[91m'
  ENDC = '\033[0m'
  BOLD = '\033[1m'
  UNDERLINE = '\033[4m'

class CheckList:

    def __init__(self):
        self.project_id = config.get(projectID)
        self.project_number = config.get(projectNumber)
        self.nar_id = config.get(NarId)
        self.region = config.get(locations)
        self.cidr = config.get(CIDR)
        self.errors_msg = []

    @staticmethod
    def format_status(status):
        if status == "OK":
            status = Colors.BOLD + Colors.OKGREEN + "OK" + Colors.ENDC
        else:
            status = Colors.BOLD + Colors.FAIL + "NOK" + Colors.ENDC
        return status

    def print_header(self):
        print(Colors.HEADER + 125 * "=")
        print(Colors.BOLD + Colors.HEADER + "CHECK LIST - OFFBOARDING")
        print(Colors.HEADER + 125 * "-" + Colors.ENDC)
        print(Colors.BOLD + "INPUTS" + Colors.ENDC)
        print(Colors.OKCYAN + 125 * "-")
        print(Colors.OKBLUE + Colors.BOLD + "PROJECT_ID:" + Colors.ENDC + self.project_id)
        print(Colors.OKBLUE + Colors.BOLD + "PROJECT_NUMBER:" + Colors.ENDC + self.project_number)
        print(Colors.OKBLUE + Colors.BOLD + "REGION:" + Colors.ENDC + self.region)
        print(Colors.OKBLUE + Colors.BOLD + "CIDR:" + Colors.ENDC + self.cidr)
        print(Colors.OKCYAN + 125 * "-" + Colors.ENDC)
    @property
    def format_time(self):
        return "[" + time.strftime("%Y-%m-%d %H:%M:%S") + "] "

    def check_project_exists(self):
        """
        Confirm if the project id in the CNE ticket exists in GCP.
        """
    request = cloudresourcemanager.projects().list()
    response = request.execute()
    if any(self.project_id in project['name'] for project in response.get('projects', [])):
        status = self.format_status("OK")
    else:
        status = self.format_status("OK")
        self.errors_msg.append("Error: Project {} doesn't exist!".format(self.project_id))
    print(self.format_time + "Checking if the project {} exists {} [{}]".format(self.project_id, 42 * ".", status))

    def check_project_number(self):
        """
        Confirm if the project number in the CNE ticket exists in GCP.
        """
    request = cloudresourcemanager.projects().list()
    response = request.execute()
    if any(str(self.project_number) in project['projectNumber'] for project in response.get('projects', [])):
        status = self.format_status("OK")
    else:
        status = self.format_status("NOK")
        self.errors_msg.append("Error: Project number {} doesn't exist!".format(self.project_number))

    print(self.format_time + "Checking if the project number {} exists {} [{}]".format(self.project_number, 47 * ".", status))

    def check_firewall_rule_status(self):
        """
        Check if there are FW rules for the project and if them are enabled.
        """
    request = compute.firewalls().list(project=self.project_id)
    response = request.execute()
    if any(str(self.nar_id) in firewall['name'] and firewall['disabled'] for firewall in
        response.get('items', [])):
        status = self.format_status("OK")
    elif any(str(self.nar_id) in firewall['name'] for firewall in response.get('items', [])):
        status = self.format_status("OK")
    else:
        status = self.format_status("NOK")
        self.errors_msg.append("Error: There is(are) FW rules for the NAR ID {}!".format(self.nar_id))
    print(self.format_time + "Checking if the FW rules was deleted for the NAR ID: {} {} [{}]".format(self.nar_id, 41 * ".", status))

    def check_reserved_ip(self):
        """
        Verify if there is reserved IP addressess in the project.
        """
    request = compute.addresses().list(project=self.project_id, region=self.region)
    response = request.execute()
    status = None
    # Partial off-boarding
    if self.cidr:
        for addresses in response.get('items', []):
            if self.subnet_contains(addresses['addresses'], self.cidr):
                status = self.format_status("NOK")
                self.errors_msg.append("Error: The IP {} is a reserved address for the project {}!".format(
                    addresses['addresses'],
                    self.project_id))

    # Full off-boarding

    elif any(len(addresses['address']) > 0 for addresses in response.get('items', [])) and not self.cidr:
        status = self.format_status("NOK")
        self.errors_msg.append("Error: There is a reserved address for the project {}!".format(self.project_id))
    else:
        status = self.format_status("OK")
    print(self.format_time + "Checking if there is reserved IPs for the project: {} {} [{}]".format(self.project_id, 22 * ".", status))
    
    def check_cluster_in_use(self):
        """
        Check if there are applications running in the cluster.
        """
        request = container.projects().zones().clusters().list(projectId=self.project_id, zone="-")
        response = request.execute()
    # Partial off-boarding
    if any(self.cidr in cluster['clusterIpv4Cidr'] for cluster in response.get('clusters', [])) and self.cidr: 
        status = self.format_status("NOK")
        self.errors_msg.append("Error: The CIDR {} is in use in the project {}! {}".format(self.cidr,
        self.project_id,
        Colors.ENDC))
    # Full off-boarding
    elif any(cluster['status'] == 'RUNNING' for cluster in response.get('clusters', [])) and not self.cidr:
        status = self.format_status("NOK")
        self.errors_msg.append("Error: There is an application in status 'RUNNING' in the project {}.".
        format(self.project_id))
    else:
        status = self.format_status("OK")
    print("{}Checking if containers are in use for the project: {} {} [{}]".format(self.format_time, self.project_id, 22 * ".", status))
    
    def subnet_contains(self, ipAddress, subnet):
        return ipaddress.IPv4Address(ipAddress) in ipaddress.IPv4Network(subnet)

    def check_compute_in_use(self):
        """
        Check if there are VM Running in the project.
        """
        status = None
    request = compute_v1.AggregatedListInstancesRequest()
    request.project = self.project_id
    agg_list = instance_client.aggregated_list(request=request)
    print(agg_list)
    if self.cidr: # If partial off-boarding
        for zone, response in agg_list:
            print(response.instance)
            if response.instances:
                for instance in response.instances:
                    if (self.subnet_contains(ipaddress.IPv4Address(instance.network_interfaces[0].network_i_p),self.cidr)) and (instance.status == 'RUNNING') and self.cidr:
                        status = self.format_status("NOK")
                        self.errors_msg.append("The VM {} is {} using IP:{}".format(instance.name,
                        instance.status.lower(),
                        instance.network_interfaces[0].network_i_p))
                    else:
                        status = self.format_status("OK")
    else: # Full off-boarding
        for zone, response in agg_list:
            if response.instances:
                for instance in response.instances:
                    if instance.status == 'RUNNING':
                        status = self.format_status("NOK")
                        self.errors_msg.append("The VM {} is {} using IP:{}".format(instance.name,
                        instance.status.lower(),
                        instance.network_interfaces[0].network_i_p))
                    else:
                        status = self.format_status("OK")
    print("{}Checking if there are VMs in use for the project: {} {} [{}]".format(self.format_time,
        self.project_id, 23 * ".", status))

    def list_errors(self):
        if len(self.errors_msg):
            print(Colors.OKCYAN + 125 * "-" + Colors.ENDC)
            print(Colors.BOLD + Colors.FAIL + "List of errors:" + Colors.ENDC)
            #[print(Colors.WARNING + "-" + error + Colors.ENDC) for error in self.errors_msg]
            print(Colors.OKCYAN + 125 * "-" + Colors.ENDC)
    def off_boarding(self):
        self.print_header()
        self.check_project_exists()
        self.check_project_number()
        self.check_firewall_rule_status()
        self.check_reserved_ip()
        self.check_cluster_in_use()
        self.check_compute_in_use()
        self.list_errors()
        print(self.format_time + "Finished!")
        print(Colors.HEADER + 125 * "=" + Colors.ENDC)

if __name__ == '__main__':
    CheckList().off_boarding()