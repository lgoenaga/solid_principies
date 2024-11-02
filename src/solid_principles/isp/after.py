import os
from dataclasses import dataclass, field
from typing import Optional, Protocol
import uuid
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
    id: Optional[str] = None


class PaymentData(BaseModel):
    amount: int
    source: str


@dataclass
class PaymentResponse:
    status: str
    amount: int
    id: Optional[str] = None
    message: Optional[str] = None


@dataclass
class ValidateData:
    def validate_customer_data(self, customer_data: CustomerData):
        if not customer_data.name:
            print("Invalid customer data: missing name")
            raise ValueError("Invalid customer data: missing name")
        if not customer_data.contact_info:
            print("Invalid customer data: missing contact info")
            raise ValueError("Invalid customer data: missing contact info")
        if (
            not customer_data.contact_info.email
            and not customer_data.contact_info.phone
        ):
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
    def notify_customer(self, customer_data: CustomerData): ...


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
        print(
            f"send the sms using {sms_gateway}: SMS sent to {phone_number}: Thank you for your payment."
        )
        return


@dataclass
class LogTransaction:
    def log_transaction(
        self, customer_data: CustomerData, payment_data: PaymentData, charge
    ):
        with open("transactions.log", "a") as log_file:
            log_file.write(f"{customer_data.name} paid {payment_data.amount}\n")
            log_file.write(f"Transaction ID: {charge.id}\n")
            log_file.write(f"Status: {charge.status}\n")


class PaymentProcessorProtocol(Protocol):
    def process_transaction(
        self, customer_data: CustomerData, payment_data: PaymentData
    ) -> PaymentResponse: ...


class RefundPaymentProtocol(Protocol):
    def refund_transaction(self, transaction_id: str) -> PaymentResponse: ...


class RecurrencePaymentProtocol(Protocol):
    def setup_recurrence(
        self, customer_data: CustomerData, payment_data: PaymentData
    ) -> PaymentResponse: ...


@dataclass
class ProcessPayment(
    PaymentProcessorProtocol, RefundPaymentProtocol, RecurrencePaymentProtocol
):
    def process_transaction(
        self, customer_data: CustomerData, payment_data: PaymentData
    ):
        stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
        try:
            charge = stripe.Charge.create(
                amount=payment_data.amount,
                currency="usd",
                source=payment_data.source,
                description="Charge for " + customer_data.name,
            )
            print("Payment successful")
            return PaymentResponse(
                status=charge["status"],
                amount=charge["amount"],
                id=charge["id"],
                message="Payment successful",
            )
        except StripeError as e:
            print("Payment failed:", e)
            return PaymentResponse(
                status="payment_failed", amount=0, id=None, message=str(e)
            )

    def refund_transaction(self, transaction_id: str) -> PaymentResponse:
        print("Refunding payment")
        return PaymentResponse(
            status="payment_refunded",
            amount=0,
            id=transaction_id,
            message="Payment refunded successfully",
        )

    def setup_recurrence(
        self, customer_data: CustomerData, payment_data: PaymentData
    ) -> PaymentResponse:
        stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
        price_id = os.getenv("STRIPE_PRICE_ID")
        try:
            customer = stripe.Customer.create(email=customer_data.contact_info.email)
            payment_method = self.__attach_payment_method(
                customer.id, payment_data.source
            )
            self.__set_default_payment_method(customer.id, payment_method.id)
            subscription = stripe.Subscription.create(
                customer=customer.id,
                items=[{"price": price_id}],
                expand=["latest_invoice.payment_intent"],
            )
            print("Recurrence payment successful")
            amount = subscription["items"]["data"][0]["price"]["unit_amount"]
            return PaymentResponse(
                status=subscription["status"],
                amount=amount,
                id=subscription.id,
                message="Recurrence payment successful",
            )
        except StripeError as e:
            print("Recurrence payment failed:", e)
            return PaymentResponse(
                status="recurrence_payment_failed", amount=0, id=None, message=str(e)
            )

    def __attach_payment_method(self, customer_id: str, payment_method_id: str):
        return stripe.PaymentMethod.attach(payment_method_id, customer=customer_id)

    def __set_default_payment_method(self, customer_id: str, payment_method_id: str):
        stripe.Customer.modify(
            customer_id, invoice_settings={"default_payment_method": payment_method_id}
        )


class OffLinePaymentProcessor(PaymentProcessorProtocol):

    def process_payments(
        self, customer_data: CustomerData, payment_data: PaymentData
    ) -> PaymentResponse:
        print("Offline payment processed successfully")
        return PaymentResponse(
            status="offline_payment_processed",
            amount=payment_data.amount,
            id=str(uuid.uuid4()),
            message="Offline payment processed successfully",
        )


@dataclass
class PaymentService:
    validate_data = ValidateData()
    validate_payment_data = ValidatePaymentData()
    process_payment: PaymentProcessorProtocol = field(default_factory=ProcessPayment)
    notify: Notify = field(default_factory=EmailNotify)
    log_transaction = LogTransaction()
    refund_payment_processor: Optional[RefundPaymentProtocol] = None
    recurrence_payment_processor: Optional[RecurrencePaymentProtocol] = None

    def process_payments(
        self, payment_data: PaymentData, customer_data: CustomerData
    ) -> PaymentResponse:
        try:
            self.validate_data.validate_customer_data(customer_data)
            self.validate_payment_data.validate_payment_data(payment_data)
            charge = self.process_payment.process_transaction(
                customer_data, payment_data
            )
            self.notify.notify_customer(customer_data)
            self.log_transaction.log_transaction(customer_data, payment_data, charge)
            return charge
        except Exception as e:
            print(f"Error processing payment: {e}")
            raise e

    def refund_payment(self, transaction_id: str) -> PaymentResponse:
        if not self.refund_payment_processor:
            raise Exception("Refund payment processor not supported")
        response = self.refund_payment_processor.refund_transaction(transaction_id)
        self.log_transaction.log_transaction(transaction_id, response)
        return response

    def setup_recurrence_payment(
        self, payment_data: PaymentData, customer_data: CustomerData
    ) -> PaymentResponse:
        if not self.recurrence_payment_processor:
            raise Exception("Recurrence payment processor not supported")
        response = self.recurrence_payment_processor.setup_recurrence(
            customer_data, payment_data
        )
        self.log_transaction.log_transaction(customer_data, payment_data, response)
        return response


if __name__ == "__main__":
    sms_notify = SMSNotify()

    payment_service = PaymentService()
    payment_service_sms = PaymentService(notify=sms_notify)
    payment_service_offline = OffLinePaymentProcessor()

    customer_data_with_email = CustomerData(
        name="John Doe", contact_info=ContactInfo(email="example@mail.com")
    )
    customer_data_with_phone = CustomerData(
        name="Platzi Python", contact_info=ContactInfo(phone="1234567890")
    )

    payment_data = PaymentData(amount=500, source="tok_mastercard")

    stripe_process_payment = ProcessPayment()

    payment_service.refund_payment_processor = stripe_process_payment
    payment_service.recurrence_payment_processor = stripe_process_payment

    payment_service.process_payments(payment_data, customer_data_with_email)
    payment_service_sms.process_payments(payment_data, customer_data_with_phone)
    payment_service_offline.process_payments(customer_data_with_email, payment_data)
