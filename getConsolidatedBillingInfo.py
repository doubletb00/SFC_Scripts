__author__ = 'Jon Hall, Britt Pearsall'
#
## Get a simplified overview of a range of billing periods
## Place APIKEY & Username in config.ini
## or pass via commandline  (example: GetNewInvoices.py -u=userid -k=apikey)
##

import SoftLayer, json, configparser, argparse, csv, xlsxwriter, re, time
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
			raise ValueError("Must specify either Username/API Key or Config File.")
			exit()

	if fedFlag:
		client = SoftLayer.Client(username=user, api_key=key, endpoint_url=fedURL)
	else:
		client = SoftLayer.Client(username=user, api_key=key)
	return client


## READ CommandLine Arguments and load configuration file
parser = argparse.ArgumentParser(description="Print a report of NEW invoices which have a non zero balance between Start and End date.")
parser.add_argument("-u", "--username", help="String: SoftLayer API Username")
parser.add_argument("-k", "--apikey", help="String: SoftLayer API Key")
parser.add_argument("-f", "--federal", help="Flag: Connect to Federal API", action='store_true')
parser.add_argument("-c", "--config", help="Filepath: config.ini file to load")
parser.add_argument("-s", "--startdate", help="String: Start Date mm/dd/yy")
parser.add_argument("-e", "--enddate", help="String: End Date mm/dd/yyyy")
parser.add_argument("-o", "--output", help="Filepath: Output File Name")

args = parser.parse_args()

client = initializeSoftLayerAPI(args.username, args.apikey, args.federal, args.config)

#
# Check argument syntax
#

if args.startdate == None:
	raise ValueError("Start date must be specified in mm/dd/yyy format")
	exit()
		
else:
	try:
		time.strptime(args.startdate, '%m/%d/%Y')
	except ValueError:
		raise ValueError("Start date must be specified in mm/dd/yyy format")
		exit()
	startdate=args.startdate

if args.enddate == None:
	raise ValueError("End date must be specified in mm/dd/yyy format")
	exit()
		
else:
	try:
		time.strptime(args.enddate, '%m/%d/%Y')
	except ValueError:
		raise ValueError("End date must be specified in mm/dd/yyy format")
		exit()
	enddate=args.enddate

if not time.strptime(startdate, '%m/%d/%Y') < time.strptime(enddate, '%m/%d/%Y'):
	raise ValueError("Start Date must be before End Date")
	exit()
	
if args.output == None:
	raise ValueError("Output file name must be specified, .csv")
	exit()
else:
	if re.match('.+\.csv', args.output):
		outputnamefull=args.output
	else:
		raise ValueError("Output file name must be specified, .csv")
		exit()

outputprefix=outputnamefull.split('.csv')[0]
outfileSheet1 = outputprefix+'_Sheet1.csv'
outfileSheet2 = outputprefix+'_Sheet2.csv'

#
# Get all invoices for the time specified
#

print()
print("Looking up invoices....")

InvoiceList = client['Account'].getInvoices(mask='createDate, closedDate, typeCode, id, invoiceTotalAmount, invoiceTopLevelItemCount, itemCount', filter={
		'invoices': {
			'createDate': {
				'operation': 'betweenDate',
				'options': [
					 {'name': 'startDate', 'value': [startdate+" 0:0:0"]},
					 {'name': 'endDate', 'value': [enddate+" 23:59:59"]}
					 ],
				},
			'typeCode': {
				'operation': 'in',
				'options': [
					{'name': 'data', 'value': ['ONE-TIME-CHARGE', 'NEW', 'RECURRING']}
				]
				},
			}
		})
		
#
# Get month headers
#

monthlist=[]
hostlist=[]
hostinfo=[]
alliteminfo=[]

for invoice in InvoiceList:
	month = invoice['createDate'][0:7]
	if month not in monthlist:
		monthlist.append(month)	

monthlist.sort

#
# Get billing information
#
print()
print("Compiling billing information....")
		
for invoice in InvoiceList:
	invoiceID = invoice['id']
	totalTopItems = invoice['invoiceTopLevelItemCount']
	totalItems = invoice['itemCount']
	month = invoice['createDate'][0:7]
	
	if invoice['invoiceTotalAmount'] != "0":
	
		limit = 10  ## set limit of record t
		for offset in range(0, totalTopItems, limit):
			someTopLevelItems = client['Billing_Invoice'].getInvoiceTopLevelItems(id=invoiceID, limit=limit, offset=offset,
								mask='id, categoryCode, hostName, domainName, description, totalRecurringAmount, totalOneTimeAmount, recurringAfterTaxAmount, oneTimeAfterTaxAmount') 
			
			for topinvoice in someTopLevelItems:
				if topinvoice['categoryCode'] == 'server' or topinvoice['categoryCode'] == 'guest_core':
					fullhostname=topinvoice['hostName']+'.'+topinvoice['domainName']
					totalCost = float(topinvoice['totalRecurringAmount'])+float(topinvoice['totalOneTimeAmount'])

					if fullhostname not in hostlist:
						hostlist.append(fullhostname)
						hostinfo.append({'Host Name':fullhostname, month:round(totalCost,2)})
					else:
						for host in hostinfo:
							if host['Host Name'] == fullhostname:
								host[month]=round(totalCost,2)
					
					
					processorCost = float(topinvoice['recurringAfterTaxAmount'])+float(topinvoice['oneTimeAfterTaxAmount'])
					alliteminfo.append({'Host Name':fullhostname, 'Item Description':topinvoice['description'], 'Month':month, 'Invoice #':invoiceID, 'Total Cost':round(processorCost,2)})
					
					childrenItems = client['Billing_Invoice_Item'].getAssociatedChildren(id=topinvoice['id'], mask='id, hostName, domainName, description, recurringAfterTaxAmount, oneTimeAfterTaxAmount')
					for i in childrenItems:
						totalCost = float(i['recurringAfterTaxAmount'])+float(i['oneTimeAfterTaxAmount'])
						alliteminfo.append({'Host Name':fullhostname, 'Item Description':i['description'], 'Month':month, 'Invoice #':invoiceID, 'Total Cost':round(totalCost,2)})
				else:
					fullhostname='<none>'
					totalCost = float(topinvoice['totalRecurringAmount'])+float(topinvoice['totalOneTimeAmount'])
					
					if fullhostname not in hostlist:
						hostlist.append(fullhostname)
						hostinfo.append({'Host Name':fullhostname, month:round(totalCost,2)})
					else:
						for host in hostinfo:
							if host['Host Name'] == fullhostname:
								if month in host.keys():
									host[month]=round(host[month]+totalCost,2)
								else:
									host[month]=round(totalCost,2)

					alliteminfo.append({'Host Name':fullhostname, 'Item Description':topinvoice['description'], 'Month':month, 'Invoice #':invoiceID, 'Total Cost':round(totalCost,2)})

#
# Write csv files
#
print()
print("Creating csv files....")

fieldnames1 = ['Host Name']+monthlist

outfile1 = open(outfileSheet1, 'w', newline='')
csvwriter1 = csv.DictWriter(outfile1, delimiter=',', fieldnames=fieldnames1)
csvwriter1.writerow(dict((fn, fn) for fn in fieldnames1))

fieldnames2 = ['Host Name', 'Item Description', 'Month', 'Invoice #', 'Total Cost']

outfile2 = open(outfileSheet2, 'w', newline='')
csvwriter2 = csv.DictWriter(outfile2, delimiter=',', fieldnames=fieldnames2)
csvwriter2.writerow(dict((fn, fn) for fn in fieldnames2))

for host in hostinfo:
	csvwriter1.writerow(host)
	
for item in alliteminfo:
	csvwriter2.writerow(item)
	
##close CSV File
outfile1.close()
outfile2.close()
