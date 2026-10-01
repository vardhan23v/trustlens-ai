"""Hold-out messages for the rule-only trust score. Run once after tuning; do not tune against it.

    python tests/score_holdout.py
"""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.services import flow, reporter
LEGIT = [
 "Kotak Bank: Your FD of Rs 1,00,000 matures on 14 Oct 2026. It will be auto-renewed unless you change instructions in the Kotak app.",
 "Your gas cylinder booking no 778812 is confirmed. Delivery expected in 2 days. Pay Rs 903 to the delivery person. -Indane",
 "Dear member, your gym membership expires in 3 days. Renew at the front desk to keep your slot.",
 "BSNL: Your broadband bill of Rs 799 is unpaid. Service will be suspended after 18 Oct. Pay at the BSNL Selfcare portal.",
 "Hey, I got a new number, save this one. See you at the wedding on Sunday!",
 "Your Zomato order is on the way. Rider Suresh 9845012345 will reach in 12 minutes.",
 "RBI Kehta Hai: Never share your OTP or card details with anyone. Jaankar baniye, satark rahiye.",
 "Canara Bank: Rs 2,000 withdrawn at ATM from A/c XX7788 on 01-10-26. If not done by you, call 18004250018 to block your card.",
 "Your visa application has been received. Processing fee of Rs 1,500 paid. Reference VFS/BLR/20261001.",
 "Meeting reminder: project review tomorrow 11 am. Please update the tracker today.",
 "Google Pay: You received Rs 350 from Anita. Check the app for details.",
 "Dear customer, your order could not be delivered today as the address was closed. We will attempt again tomorrow. -Blue Dart",
 "Exam fee of Rs 1,200 must be paid by 20 Oct at the college office. Students with dues will not be allowed to appear.",
 "Your Ola ride OTP is 7392. Share it with the driver to start the trip.",
 "LIC: Your policy 778899001 has lapsed. Visit your nearest LIC branch to revive it.",
]
SCAM = [
 "Dear customer your Canara bank account will be blocked today. Update PAN immediately click http://canara-kyc.online/pan",
 "Your Blue Dart parcel is on hold due to incomplete address. Update within 12 hours at bluedart-track.top/addr and pay Rs 25.",
 "I am calling from Mumbai cyber crime. Your Aadhaar is used in money laundering. Do not disconnect, transfer funds to the safe account for RBI verification immediately.",
 "Earn Rs 8000 daily from home by rating hotels. Pay Rs 500 activation fee to start. WhatsApp 9123409876 now.",
 "Dear user your SBI reward points Rs 9,850 will expire today. Click sbi-rewards.club to redeem now and enter your card number.",
 "Your Paytm wallet KYC is incomplete. Wallet will be blocked in 24 hrs. Call 8240123456 immediately.",
 "Congratulations! Your mobile number has won a lucky draw of Rs 5,00,000 from Jio. Send your account number and pay tax amount first.",
 "Hi, this is my new number. I am stuck at the hospital, please send Rs 30,000 to 9000012345@paytm right now.",
 "Electricity bill pending. Your power will be cut at 10 pm tonight. Call the lineman on 9440012345 immediately.",
 "HDFC Bank: Your account is suspended due to incomplete KYC. Verify now: http://bit.ly/hdfc-kyc",
 "Instant loan approved Rs 2 lakh. Pay Rs 1,499 processing fee first to receive the amount today. Limited time offer.",
 "Your Amazon Prime will be terminated. Update card details at http://45.33.12.9/prime to continue.",
 "TRAI notice: your number is involved in illegal activity and will be disconnected in 2 hours. Press 1 to speak to an officer.",
 "Dear customer, share the OTP sent to your number to receive your refund of Rs 4,999. Call 7890123456 now.",
 "Crypto investment: guaranteed 200% returns in 10 days. Transfer Rs 10,000 to join. Contact on Telegram immediately.",
]
for label, items, ok in (("legit", LEGIT, {"LOW"}), ("scam", SCAM, {"HIGH"})):
    n = 0
    for t in items:
        r = reporter.build(flow.deterministic_only("text", t, b"", "", "eval"))
        good = r.risk_level in ok
        n += good
        if not good:
            print(f"MISS {label} {r.risk_level} {r.trust_score} | {t[:75]}\n     {[(s.key, s.severity) for s in r.signals]}")
    print(label, n, "/", len(items))

