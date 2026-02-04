from abc import ABC, abstractmethod

class BaseProvider(ABC):
    def __init__(self, username, password, api_url):
        self.username = username
        self.password = password
        self.api_url = api_url

    @abstractmethod
    def connect(self):
        """Entegratöre bağlantı kurar"""
        pass

    @abstractmethod
    def send_invoice(self, ubl_xml, ettn, alici_vkn, alici_alias):
        """
        Faturayı gönderir.
        Return: (True/False, Mesaj/TakipNo)
        """
        pass

    @abstractmethod
    def check_status(self, ettn):
        """Fatura durumunu sorgular"""
        pass
    
    @abstractmethod
    def is_euser(self, vkn):
        """
        Mükellefin E-Fatura kullanıcısı olup olmadığını sorgular.
        Return: (True/False, PostaKutusuAliasi)
        """
        pass