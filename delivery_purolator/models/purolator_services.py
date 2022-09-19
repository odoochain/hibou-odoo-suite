from requests import Session
from requests.auth import HTTPBasicAuth
from zeep import Client
from zeep.cache import SqliteCache
from zeep.transports import Transport
from odoo.exceptions import UserError


class PurolatorClient(object):
    
    # clients and factories
    _shipping_client = None
    @property
    def shipping_client(self):
        if not self._shipping_client:
            self._shipping_client = self._get_client('/EWS/V2/Shipping/ShippingService.asmx?wsdl')
        return self._shipping_client

    _shipping_factory = None
    @property
    def shipping_factory(self):
        if not self._shipping_factory:
            self._shipping_factory = self.shipping_client.type_factory('ns1')
        return self._shipping_factory

    _shipping_documents_client = None
    @property
    def shipping_documents_client(self):
        if not self._shipping_documents_client:
            self._shipping_documents_client = self._get_client('/PWS/V1/ShippingDocuments/ShippingDocumentsService.asmx?wsdl', version='1.3')
        return self._shipping_documents_client

    _shipping_documents_factory = None
    @property
    def shipping_documents_factory(self):
        if not self._shipping_documents_factory:
            self._shipping_documents_factory = self.shipping_documents_client.type_factory('ns1')
        return self._shipping_documents_factory
    
    def __init__(self, api_key, password, activation_key, account_number, is_prod):
        self.api_key = api_key
        self.password = password
        self.activation_key = activation_key
        self.account_number = account_number
        self._wsdl_base = "https://devwebservices.purolator.com"
        if is_prod:
            self._wsdl_base = "https://webservices.purolator.com"
            
        session = Session()
        session.auth = HTTPBasicAuth(self.api_key, self.password)
        self.transport = Transport(cache=SqliteCache(), session=session)
        
    def _get_client(self, wsdl_path, version='2.0'):
        # version added because shipping documents needs a different one
        client = Client(self._wsdl_base + wsdl_path,
                        transport=self.transport)
        request_context = client.get_element('ns1:RequestContext')
        header_value = request_context(
            Version=version,
            Language='en',
            GroupID='xxx',
            RequestReference='RatingExample',  # TODO need to paramatarize this or something, doesn't make sense to shipment, maybe GroupID
            UserToken=self.activation_key,
        )
        client.set_default_soapheaders([header_value])
        return client        
            
    def get_quick_estimate(self, sender_postal_code, receiver_address, package_type, total_weight):
        """ Call GetQuickEstimate
        
        :param sender_postal_code: string
        :param receiver_address: dict {'City': string,
                                       'Province': string,
                                       'Country': string,
                                       'PostalCode': string}
        :param package_type: string
        :param total_weight: float (in pounds)
        :returns: dict {'shipments': list, 'error': string or False}
        """
        client = self._get_client('/EWS/V2/Estimating/EstimatingService.asmx?wsdl')
        response = client.service.GetQuickEstimate(
            BillingAccountNumber=self.account_number,
            SenderPostalCode=sender_postal_code,
            ReceiverAddress=receiver_address,
            PackageType=package_type,
            TotalWeight={  # TODO FIX/paramatarize
                'Value': 10.0,
                'WeightUnit': 'lb',
                },
            )
        errors = response['body']['ResponseInformation']['Errors']
        if errors:
            return {
                'shipments': False,
                'error': '\n'.join(['%s: %s' % (error['Code'], error['Description']) for error in errors['Error']]),
            }
        shipments = response['body']['ShipmentEstimates']['ShipmentEstimate']
        if shipments:
            return {
                'shipments': shipments,
                'error': False,
            }
        return {
            'shipments': False,
            'error': 'Purolator service did not return any matching rates.',
        }
        
    def shipment_request(self):
        shipment = self.shipping_factory.Shipment()
        shipment.SenderInformation = self.shipping_factory.SenderInformation()
        shipment.SenderInformation.Address = self.shipping_factory.Address()
        shipment.SenderInformation.Address.PhoneNumber = self.shipping_factory.PhoneNumber()
        shipment.ReceiverInformation = self.shipping_factory.ReceiverInformation()
        shipment.ReceiverInformation.Address = self.shipping_factory.Address()
        shipment.ReceiverInformation.Address.PhoneNumber = self.shipping_factory.PhoneNumber()
        shipment.PackageInformation = self.shipping_factory.PackageInformation()
        shipment.PackageInformation.TotalWeight = self.shipping_factory.TotalWeight()
        shipment.PackageInformation.PiecesInformation = self.shipping_factory.ArrayOfPiece()
        shipment.PaymentInformation = self.shipping_factory.PaymentInformation()
        return shipment
    
    def shipment_add_picking_packages(self, shipment, carrier, picking, packages):
        # note that no package can be less than 1lb, so we fix that here...
        # for the package to be allowed, it must be the same service
        shipment.PackageInformation.ServiceID = carrier.purolator_service_type
        
        total_weight_value = 0.0
        total_pieces = len(packages) or 1
        if not packages:
            # setup default package
            package_weight = picking.shipping_weight  # TODO need conversion (lb) below
            if package_weight < 1.0:
                package_weight = 1.0
            total_weight_value += package_weight
            package_type = carrier.purolator_default_package_type_id
            p = self.shipping_factory.Piece(
                Weight={
                    'Value': str(package_weight),
                    'WeightUnit': 'lb',
                },
                Length={
                    'Value': str(package_type.packaging_length),  # TODO need conversion
                    'DimensionUnit': 'in', 
                },
                Width={
                    'Value': str(package_type.width),  # TODO need conversion
                    'DimensionUnit': 'in', 
                },
                Height={
                    'Value': str(package_type.height),  # TODO need conversion
                    'DimensionUnit': 'in', 
                },
            )
            shipment.PackageInformation.PiecesInformation.Piece.append(p)
        else:
            for package in packages:
                package_weight = package.shipping_weight  # TODO need conversion (lb) below
                if package_weight < 1.0:
                    package_weight = 1.0
                package_type = package.package_type_id
                total_weight_value += package_weight
                p = self.shipping_factory.Piece(
                    Weight={
                        'Value': str(package_weight),
                        'WeightUnit': 'lb',
                    },
                    Length={
                        'Value': str(package_type.packaging_length),  # TODO need conversion
                        'DimensionUnit': 'in', 
                    },
                    Width={
                        'Value': str(package_type.width),  # TODO need conversion
                        'DimensionUnit': 'in', 
                    },
                    Height={
                        'Value': str(package_type.height),  # TODO need conversion
                        'DimensionUnit': 'in', 
                    },
                )
                # TODO p.Options.OptionIDValuePair  (ID='SpecialHandling', Value='true')
                # can we do per-package signature requirements?
                # Packaging specific codes?
                shipment.PackageInformation.PiecesInformation.Piece.append(p)
        
        shipment.PackageInformation.TotalWeight.Value = str(total_weight_value)
        shipment.PackageInformation.TotalWeight.WeightUnit = 'lb'
        shipment.PackageInformation.TotalPieces = str(total_pieces)

    def shipment_create(self, shipment, printer_type='Thermal'):
        response = self.shipping_client.service.CreateShipment(
            Shipment=shipment,
            PrinterType=printer_type,
        )
        return response.body
    
    def document_by_pin(self, pin, document_type='', output_type='ZPL'):
        # TODO document_type?
        document_criterium = self.shipping_documents_factory.ArrayOfDocumentCriteria()
        document_criterium.DocumentCriteria.append(self.shipping_documents_factory.DocumentCriteria(
            PIN=pin,
        ))
        response = self.shipping_documents_client.service.GetDocuments(
            DocumentCriterium=document_criterium,
            OutputType=output_type,
            Synchronous=True,
        )
        return response.body
