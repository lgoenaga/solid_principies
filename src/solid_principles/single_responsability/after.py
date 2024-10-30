import os
from dataclasses import dataclass
import stripe
from stripe.error import StripeError
from stripe import Charge
from dotenv import load_dotenv
from email.mime.text import MIMEText


# Load environment variables from .env file
_ = load_dotenv()

@dataclass
class ValidateData:
    def validate_customer_data(self, customer_data):
        if not customer_data.get("name"):
            print("Invalid customer data: missing name")
            raise ValueError("Invalid customer data: missing name")
        if not customer_data.get("contact_info"):
            print("Invalid customer data: missing contact info")
            raise ValueError("Invalid customer data: missing contact info")
        return True

@dataclass
class ValidatePaymentData:
    def validate_payment_data(self, payment_data):         
        if not payment_data.get("source"):
            print("Invalid payment data")
            raise ValueError("Invalid payment data")
        return True

@dataclass
class NotifyCustomer:
    def notify_customer(self, customer_data, charge):
        if "email" in customer_data["contact_info"]:
            msg = MIMEText("Thank you for your payment.")
            msg["Subject"] = "Payment Confirmation"
            msg["From"] = "no-reply@example.com"
            msg["To"] = customer_data["contact_info"]["email"]
            print("Email sent to", customer_data["contact_info"]["email"])
        elif "phone" in customer_data["contact_info"]:
            phone_number = customer_data["contact_info"]["phone"]
            sms_gateway = "the custom SMS Gateway"
            print(f"send the sms using {sms_gateway}: SMS sent to {phone_number}: Thank you for your payment.")
        else:
            print("No valid contact information for notification")

@dataclass
class LogTransaction:
    def log_transaction(self, customer_data, payment_data, charge):
        with open("transactions.log", "a") as log_file:
            log_file.write(f"{customer_data['name']} paid {payment_data['amount']}\n")
            log_file.write(f"Payment status: {charge['status']}\n")

@dataclass
class ProcessPayment:
    def process_transaction(self, customer_data, payment_data):
        stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
        try:
            charge = stripe.Charge.create(
                amount=payment_data["amount"],
                currency="usd",
                source=payment_data["source"],
                description="Charge for " + customer_data["name"],
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
    process_payment = ProcessPayment()
    notify_customer = NotifyCustomer()
    log_transaction = LogTransaction()

    def process_payments(self, payment_data, customer_data) -> Charge:
        try:
            self.validate_data.validate_customer_data(customer_data)
            self.validate_payment_data.validate_payment_data(payment_data)
            charge = self.process_payment.process_transaction(customer_data, payment_data)
            self.notify_customer.notify_customer(customer_data, charge)
            self.log_transaction.log_transaction(customer_data, payment_data, charge)
            return charge
        except Exception as e:
            print(f"Error processing payment: {e}")
            raise e

if __name__ == "__main__":
    payment_service = PaymentService()

    customer_data_with_email = {
        "name": "John Doe",
        "contact_info": {"email": "e@mail.com"},
    }
    customer_data_with_phone = {
        "name": "Platzi Python",
        "contact_info": {"phone": "1234567890"},
    }

    payment_data = {"amount": 500, "source": "tok_mastercard", "cvv": 123}

    payment_service.process_payments(payment_data, customer_data_with_email)
    payment_service.process_payments(payment_data, customer_data_with_phone)
