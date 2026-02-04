import uuid
import hashlib

def get_hardware_id():
    # uuid.getnode() cihazın fiziksel ağ kartı (MAC) adresini alır.
    # Bu değer her cihazda (PC, Laptop, Telefon) farklıdır.
    mac_address = hex(uuid.getnode())
    
    # Bu değeri bir "tuz" ile karıştırıp hashleyelim
    combined = f"MUHASEBE-V1-{mac_address}"
    return hashlib.sha256(combined.encode()).hexdigest().upper()