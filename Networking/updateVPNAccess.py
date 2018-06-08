from __future__ import print_function

__author__ = 'Britt Pearsall, Scott Moonen'

#
## Update a user's VPN access via manually assigning subnets
## Place APIKEY & Username in config.ini
## or pass via commandline  (example: updateVPNAccess.py -u=userid -k=apikey)
##

import SoftLayer, json, configparser, argparse, re

fedURL='https://api.service.usgov.softlayer.com/xmlrpc/v3.1/'
commPubURL=SoftLayer.API_PUBLIC_ENDPOINT
commPrivURL=SoftLayer.API_PRIVATE_ENDPOINT

def initializeSoftLayerAPI(user, key, fedFlag, configfile):
	if user == None and key == None:
		if configfile != None:
			config = configparser.ConfigParser()
			config.read(configfile)
			
			user=config['api']['username']
			key=config['api']['apikey']
		else:
			print("Username/API Key or Config File must be specified.")
			exit()

	if fedFlag:
		client = SoftLayer.Client(username=user, api_key=key, endpoint_url=fedURL)
	else:
		client = SoftLayer.Client(username=user, api_key=key)
	return client


## READ CommandLine Arguments and load configuration file
parser = argparse.ArgumentParser(description="Update a user's VPN access via manual assignment of subnets")
parser.add_argument("-u", "--username", help="String: SoftLayer API Username")
parser.add_argument("-k", "--apikey", help="String: SoftLayer API Key")
parser.add_argument("-f", "--federal", help="Flag: Connect to Federal API", action='store_true')
parser.add_argument("-c", "--config", help="Filepath: config.ini file to load")
parser.add_argument("-a", "--add", help="Flag: Add subnets/IPs to existing access", action='store_true')
parser.add_argument("-r", "--replace", help="Flag: Update access to specified subnets/IPs", action='store_true')
parser.add_argument("-uu", "--updateUser", help="String: SoftLayer User to Update")
parser.add_argument("-ip", "--ip", help="String: IP(s) to access", nargs='*')
parser.add_argument("-s", "--subnet", help="String: Subnet(s) to access", nargs='*')

args = parser.parse_args()

client = initializeSoftLayerAPI(args.username, args.apikey, args.federal, args.config)
	
if args.updateUser == None:
	raise ValueError("Must specify a user to update")
	exit()

if args.add and args.replace:
	raise ValueError("Must choose to add (-a) or replace (-r), not both")
	exit()

if not args.add and not args.replace:
	raise ValueError("Must choose to add (-a) or replace (-r)")
	exit()
	
if args.ip == None and args.subnet == None:
	raise ValueError("Must specify IP(s) or subnet(s) for user update")
	exit()
	
allUsers = client['Account'].getUsers(mask='id,username')

for u in allUsers:
	if args.updateUser == u['username']:
		updateUser = client['User_Customer'].getObject(id=u['id'], mask='vpnManualConfig, id, username, overrides, sslVpnAllowedFlag')

newOverrides = []
userSubnetIds = []		
		
if args.add:
	newOverrides = updateUser['overrides']
	for o in updateUser['overrides']:
		userSubnetIds.append(o['subnetId'])
		client['SoftLayer_Network_Service_Vpn_Overrides'].deleteObject(id=o['id'])
if args.replace:
	for o in updateUser['overrides']:
		client['SoftLayer_Network_Service_Vpn_Overrides'].deleteObject(id=o['id'])
	
allSubnets = client['Account'].getPublicSubnets(mask='id,displayLabel,ipAddresses.ipAddress')
allSubnets = allSubnets+client['Account'].getPrivateSubnets(mask='id,displayLabel,ipAddresses.ipAddress')

if args.subnet:
	for s in args.subnet:
		doesExist = False
		if re.match('10\.', s) or re.match('100\.', s):
			print
			for sn in allSubnets:
				if s in sn['displayLabel']:
					doesExist = True
					if sn['id'] not in userSubnetIds:
						newOverrides.append({'subnetId': sn['id'], 'userId': updateUser['id']})
						userSubnetIds.append(sn['id'])
			if not doesExist:
				print("Subnet "+s+" does not exist in this account, subnet will be ignored.")
		else:
			raise ValueError("VPN only applies to private subnets/IP addresses.")
			exit()

if args.ip:
	for i in args.ip:
		doesExist = False
		if re.match('10\.', i) or re.match('100\.', i):
			for sn in allSubnets:
				for ips in sn['ipAddresses']:
					if i == ips['ipAddress']:
						doesExist = True
						if sn['id'] not in userSubnetIds:
							newOverrides.append({'subnetId': sn['id'], 'userId': updateUser['id']})
							userSubnetIds.append(sn['id'])
			if not doesExist:
				print("IP address "+i+" does not exist in this account, IP address will be ignored.")
		else:
			raise ValueError("VPN only applies to private subnets/IP addresses.")
			exit()

if not updateUser['sslVpnAllowedFlag'] :
	print ("SSL VPN is not enabled for user "+updateUser['username']+", enabling")
	client['SoftLayer_User_Customer'].editObject({ 'sslVpnAllowedFlag': True }, id = updateUser['id'])

if not updateUser['vpnManualConfig'] :
	print ("Manual VPN subnet configuration is not set for user "+updateUser['username']+", enabling")
	client['SoftLayer_User_Customer'].editObject({ 'vpnManualConfig': True }, id = updateUser['id'])
	
client['SoftLayer_Network_Service_Vpn_Overrides'].createObjects(newOverrides)
client['SoftLayer_User_Customer'].updateVpnUser(id=updateUser['id'])

print("User "+updateUser['username']+" VPN access has been updated.")
