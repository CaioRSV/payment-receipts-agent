import asyncio
import os
import sys

# Ensure the project root is in the python path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app.services.database import init_db
from app.services.receipts import process_direct_receipt, DirectReceiptRequest

async def main():
    # Initialize the database structure
    init_db()
    
    # Define a test request payload
    request = DirectReceiptRequest(
        payment_day=25,
        payment_month=7,
        payment_year=2026,
        referred_month="JULY.2026",
        signer_name="MÁRCIA SANTOS DA SILVA VERÇOSA",
        signer_address="RUA JOÃO MURILO DE OLIVEIRA, 142, SÃO VICENTE DE PAULO.",
        location="VITÓRIA-PE",
        pt_br=True,
        body_text="RECEBI, DA SRA. WELYTÂNIA MOURA BEZERRA DE OLIVEIRA, A QUANTIA DE R$ 800,00 (OITOCENTOS REAIS), REFERENTE AO PAGAMENTO DO ALUGUEL DO MÊS DE {ref_month} DA CASA SITUADA NA RUA AGAMENOM MAGALHÃES, 227, LIVRAMENTO, VITÓRIA-PE."
    )
    
    print("Generating test receipt...")
    try:
        result = await process_direct_receipt(request)
        print("\n=== Success! ===")
        print(f"Status: {result.status}")
        print(f"Referred Month: {result.referred_month}")
        print(f"Message: {result.formatted_message}")
        print(f"Image saved to: {result.image_path}")
    except Exception as e:
        print(f"Error during receipt generation: {e}")

if __name__ == "__main__":
    asyncio.run(main())
