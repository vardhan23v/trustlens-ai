"""Labelled message set for the deterministic part of the trust score (no Gemini needed).

    python tests/score_eval.py        # prints every miss and the accuracy

`want` is the acceptable risk band(s) from rules alone. Legitimate messages must never be HIGH and
should be LOW; scams should be HIGH (MEDIUM tolerated only where rules alone cannot know more).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services import flow, reporter  # noqa: E402

LEGIT = [
    "Your OTP for login to SBI YONO is 482913. Valid for 10 minutes. Do not share this OTP with anyone. -SBI",
    "123456 is your Amazon OTP. Do not share it with anyone.",
    "Rs.1,250.00 debited from A/c XX4321 on 01-10-26 via UPI to SWIGGY. Avl Bal Rs.18,402.11. Not you? Call 18001234 -HDFC Bank",
    "INR 45,000.00 credited to your A/c XX9911 on 30-09-26 by NEFT from INFOSYS LTD. -ICICI Bank",
    "Dear Customer, your HDFC Bank Credit Card statement is ready. Total due Rs 12,430, due date 15 Oct 2026. View at https://www.hdfcbank.com/statement",
    "Your Amazon order #402-1193 has been shipped and will arrive by Friday. Track at https://www.amazon.in/orders",
    "Your Flipkart order is out for delivery today. Delivery executive Ramesh will call you. Track: https://fkrt.it/ab12cd",
    "IRCTC: PNR 2456789012, Train 12627, 05-Oct-26, SBC to NDLS, S4 32, Fare Rs 845. Happy journey.",
    "Reminder: Your Airtel bill of Rs 599 is due on 10 Oct. Pay on the Airtel Thanks app or https://www.airtel.in/pay",
    "Dear student, the odd semester examinations will commence on 10 November 2026. Hall tickets will be available on the student portal from 3 November.",
    "Hi team, the meeting is moved to 4 pm today. Please confirm your availability.",
    "Dear customer, periodic KYC update is due for your SBI account. Please visit your home branch or use https://www.onlinesbi.sbi to update. -SBI",
    "Your Jio recharge of Rs 299 was successful. Validity 28 days. Thank you for choosing Jio.",
    "UIDAI: Your Aadhaar update request has been received. URN 1234/12345/12345. Track status at https://uidai.gov.in",
    "Income Tax Department: Your ITR for AY 2026-27 has been processed. Intimation u/s 143(1) sent to your registered email. Visit https://www.incometax.gov.in",
    "Happy Diwali from all of us at Infosys! Offices will remain closed on 20 October.",
    "Your appointment with Dr. Rao is confirmed for 6 Oct at 10:30 AM. Reply YES to confirm or call the clinic to reschedule.",
    "PhonePe: You paid Rs 240 to Fresh Mart. UPI Ref 627345118822. Balance may take a few minutes to update.",
    "Electricity bill for consumer no 4455667 is Rs 1,820. Last date for payment 12 Oct 2026. Pay at the BESCOM office or official app.",
    "Never share your PIN, CVV or OTP with anyone. Axis Bank will never ask for these details.",
    "Congratulations on completing your onboarding at TCS! Your joining date is 14 Oct 2026. HR will contact you from an @tcs.com address.",
    "Dear parent, school will remain closed tomorrow due to heavy rain. Classes resume on Monday.",
    "Your Netflix subscription has been renewed for Rs 649. Manage your plan at https://www.netflix.com/account",
    "Google: New sign-in to your account from Chrome on Windows. If this was you, no action is needed. Review activity at https://myaccount.google.com",
    "Your LIC premium of Rs 5,400 for policy 123456789 is due on 28 Oct 2026. Please ignore if already paid.",
]
SCAM = [
    "SBI Alert: Dear customer, your SBI YONO account KYC has expired today. Your account will be blocked within 24 hours. Update KYC immediately by clicking bit.ly/sbi-kyc-2026 and enter the OTP to verify. -SBI",
    "Your parcel could not be delivered. Pay Rs. 49 re-delivery fee at indiapost-redelivery.top within 12 hours.",
    "Dear user your HDFC netbanking will be suspended today. Please update your PAN number immediately http://hdfc-netbanking-verify.xyz/login",
    "Congratulations! You have won Rs 25,00,000 in KBC lottery. To claim pay processing fee of Rs 8,500 and send your Aadhaar number and bank details on WhatsApp 9876543210.",
    "Electricity power will be disconnected tonight at 9.30 pm because your previous month bill was not updated. Immediately call electricity officer 8123456789.",
    "Job offer from Amazon: work from home, earn Rs 5000 daily. Pay registration fee Rs 999 to confirm your seat. Contact on Telegram now.",
    "Your Paytm KYC has been suspended. Paytm office will block your account within 24 hrs. Call customer care 7001234567 immediately.",
    "Income Tax refund of Rs 15,490 approved. Submit your bank account and card number to receive it: http://incometax-refund.online/claim",
    "Dear customer, your SBI debit card is blocked. To unblock share your card number, CVV and OTP with our executive calling you.",
    "This is from Cyber Crime Police. A case is registered on your Aadhaar. Legal action and arrest within 2 hours unless you transfer Rs 50,000 security deposit.",
    "ICICI Bank: Your account has been temporarily frozen. Verify your identity now at https://icici-bank.secure-login.top/verify to avoid suspension.",
    "Netflix: your payment failed. Update payment details within 24 hours at http://netflix-billing-update.xyz or your account will be terminated.",
    "Aapka bank account band ho jayega. KYC karo abhi, link par click karo: tinyurl.com/kyc-upd8 aur OTP batao.",
    "TCS offer letter: You are selected. Pay refundable laptop deposit of Rs 4,500 to hr.tcs.recruit@gmail.com UPI id tcsjobs@ybl today only.",
    "Your Amazon account is locked due to suspicious activity. Confirm your password here: http://192.168.44.12/amazon/login",
    "Customs: your international parcel is held. Pay customs clearance charge Rs 2,350 immediately at dhl-india-customs.club to avoid penalty.",
    "Dear Jio user, you won a free iPhone. Click here www.jio-luckydraw.live and enter your card number to pay Rs 99 delivery charge.",
    "RBI notice: your account is flagged for money laundering. To avoid arrest transfer amount to the RBI safe account immediately. Send OTP for verification.",
    "WhatsApp will start charging from tomorrow. Forward this to 10 contacts and verify your number at wa-verify.icu to keep your account free.",
    "URGENT: Your PhonePe wallet will be blocked. Complete KYC now by downloading this app and share the code you receive.",
    "Your SIM will be blocked in 2 hours as per TRAI. Press 1 or call 9988776655 immediately to verify your Aadhaar number.",
    "Dear customer, Rs 9,999 will be debited for your subscription. If not you, call now 8899001122 and give the OTP to cancel.",
    "Bank of Baroda: pending KYC. Your account will be closed. Update at https://bob-kyc.rest/update immediately.",
    "Hi mom, I lost my phone, this is my new number. Please send money Rs 20,000 urgently to this UPI id rahul99@okaxis, will explain later.",
    "LinkedIn recruiter: part time job, Rs 3000 per day. Pay joining fee and training fee to start. Limited seats, act now.",
]


def band(text: str):
    s = flow.deterministic_only("text", text, b"", "", "eval")
    r = reporter.build(s)
    return r.risk_level, r.trust_score, [(x.key, x.severity) for x in r.signals]


def main() -> int:
    miss = 0
    stats = {"legit": {"LOW": 0, "MEDIUM": 0, "HIGH": 0}, "scam": {"LOW": 0, "MEDIUM": 0, "HIGH": 0}}
    for label, items, ok in (("legit", LEGIT, {"LOW"}), ("scam", SCAM, {"HIGH"})):
        for t in items:
            b, score, sig = band(t)
            stats[label][b] += 1
            if b not in ok:
                miss += 1
                print(f"MISS {label:5s} {b:6s} {score:3d} | {t[:70]}\n      {sig}")
    print(stats)
    total = len(LEGIT) + len(SCAM)
    print(f"correct band: {total - miss}/{total}")
    return miss


if __name__ == "__main__":
    main()
