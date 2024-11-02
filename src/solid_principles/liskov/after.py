import os
from dataclasses import dataclass, field
from typing import Optional, Protocol
import stripe
from stripe.error import StripeError
from stripe import Charge
from dotenv import load_dotenv
from email.mime.text import MIMEText
from pydantic import BaseModel

# Load environment variables from .env file
_ = load_dotenv()

class ContactInfo(BaseModel):
    email: Optional[str] = None
    phone: Optional[str] = None

class CustomerData(BaseModel):
    name: str
    contact_info: ContactInfo

class PaymentData(BaseModel):
    amount: int
    source: str

@dataclass
class ValidateData:
    def validate_customer_data(self, customer_data: CustomerData):
        if not customer_data.name:
            print("Invalid customer data: missing name")
            raise ValueError("Invalid customer data: missing name")
        if not customer_data.contact_info:
            print("Invalid customer data: missing contact info")
            raise ValueError("Invalid customer data: missing contact info")
        if not customer_data.contact_info.email and not customer_data.contact_info.phone:
            print("Invalid customer data: missing email or phone")
            raise ValueError("Invalid customer data: missing email or phone")
        return

@dataclass
class ValidatePaymentData:
    def validate_payment_data(self, payment_data: PaymentData):
        if not payment_data.amount or not payment_data.source:
            print("Invalid payment data")
            raise ValueError("Invalid payment data")
        return True

class Notify(Protocol):
    '''Protocol to define the notify_customer method
    This protocol defines the notify_customer method.  
    This method should be implemented by any class 
    that wants to notify the customer about the payment status.
    '''
    def notify_customer(self, customer_data: CustomerData): 
        '''Method to notify the customer
        :param customer_data: CustomerData object
        :type customer_data: CustomerData
        '''
        ...

@dataclass
class EmailNotify(Notify):
    def notify_customer(self, customer_data: CustomerData):
            msg = MIMEText("Thank you for your payment.")
            msg["Subject"] = "Payment Confirmation"
            msg["From"] = "no-reply@example.com"
            msg["To"] = customer_data.contact_info.email
            print("Email sent to", customer_data.contact_info.email)
            return 

@dataclass
class SMSNotify(Notify):
    def notify_customer(self, customer_data: CustomerData):
            phone_number = customer_data.contact_info.phone
            sms_gateway = "the custom SMS Gateway"
            print(f"send the sms using {sms_gateway}: SMS sent to {phone_number}: Thank you for your payment.")
            return

@dataclass
class LogTransaction:
    def log_transaction(self, customer_data: CustomerData, payment_data: PaymentData, charge):
        with open("transactions.log", "a") as log_file:
            log_file.write(f"{customer_data.name} paid {payment_data.amount}\n")
            log_file.write(f"Payment status: {charge['status']}\n")

class PaymentProcessor(Protocol):
    '''Protocol to define the process_transaction method
    This protocol defines the process_transaction method.
    This method should be implemented by any class
    that wants to process the payment.
    '''
    def process_transaction(self, customer_data: CustomerData, payment_data: PaymentData) -> Charge:
        '''Method to process the payment
        :param customer_data: CustomerData object
        :type customer_data: CustomerData
        :param payment_data: PaymentData object
        :type payment_data: PaymentData
        :return: Charge object
        :rtype: Charge
        '''
        ...

@dataclass
class ProcessPayment(PaymentProcessor):
    def process_transaction(self, customer_data: CustomerData, payment_data: PaymentData):
        stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
        try:
            charge = stripe.Charge.create(
                amount=payment_data.amount,
                currency="usd",
                source=payment_data.source,
                description="Charge for " + customer_data.name,
            )
            print("Payment successful")
            return charge
        except StripeError as e:
            print("Payment failed:", e)
            raise e

@dataclass
class PaymentService:
    validate_data = ValidateData()
    validate_payment_data = ValidatePaymentData()
    process_payment: PaymentProcessor = field(default_factory=ProcessPayment)
    notify: Notify = field(default_factory=EmailNotify)
    log_transaction = LogTransaction()

    def process_payments(self, payment_data: PaymentData, customer_data: CustomerData) -> Charge:
        try:
            self.validate_data.validate_customer_data(customer_data)
            self.validate_payment_data.validate_payment_data(payment_data)
            charge = self.process_payment.process_transaction(customer_data, payment_data)
            self.notify.notify_customer(customer_data)
            self.log_transaction.log_transaction(customer_data, payment_data, charge)
            return charge
        except Exception as e:
            print(f"Error processing payment: {e}")
            raise e

if __name__ == "__main__":
    sms_notify = SMSNotify()
    payment_service = PaymentService()
    payment_service_sms = PaymentService(notify=sms_notify)

    customer_data_with_email = CustomerData(
        name="John Doe",
        contact_info=ContactInfo(email="example@mail.com")
    )
    customer_data_with_phone = CustomerData(
        name="Platzi Python",
        contact_info=ContactInfo(phone="1234567890")
    )

    payment_data = PaymentData(amount=500, source="tok_mastercard")

    payment_service.process_payments(payment_data, customer_data_with_email)
    payment_service_sms.process_payments(payment_data, customer_data_with_phone)
