"""
extractor パッケージ
ドキュメント種別ごとのエクストラクタを提供する。
"""
from extractor.invoice import InvoiceExtractor
from extractor.delivery import DeliveryExtractor
from extractor.order import OrderExtractor

__all__ = ["InvoiceExtractor", "DeliveryExtractor", "OrderExtractor"]
