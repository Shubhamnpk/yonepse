"""
Floor Sheet Helper Utilities

This module provides utilities for working with the optimized floor sheet format.
"""

import json
import os
from typing import List, Dict, Any


def load_floor_sheet(date_str: str, data_dir: str = None) -> Dict[str, Any]:
    """
    Load floor sheet data for a specific date.
    
    Args:
        date_str: Date in YYYY-MM-DD format
        data_dir: Path to data directory (default: ../data)
    
    Returns:
        Dict with date, totals, and transactions array
    """
    if data_dir is None:
        data_dir = os.path.join(os.path.dirname(__file__), '..', 'data')
    
    daily_path = os.path.join(data_dir, 'floor_sheet', 'daily', f'{date_str}.json')
    
    if not os.path.exists(daily_path):
        return None
    
    with open(daily_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def load_lookups(data_dir: str = None) -> tuple:
    """
    Load stock and broker lookup tables.
    
    Returns:
        Tuple of (stocks_lookup, brokers_lookup)
    """
    if data_dir is None:
        data_dir = os.path.join(os.path.dirname(__file__), '..', 'data')
    
    lookups_dir = os.path.join(data_dir, 'floor_sheet', 'lookups')
    
    stocks_path = os.path.join(lookups_dir, 'stocks.json')
    brokers_path = os.path.join(lookups_dir, 'brokers.json')
    
    stocks = {}
    brokers = {}
    
    if os.path.exists(stocks_path):
        with open(stocks_path, 'r', encoding='utf-8') as f:
            stocks = json.load(f)
    
    if os.path.exists(brokers_path):
        with open(brokers_path, 'r', encoding='utf-8') as f:
            brokers = json.load(f)
    
    return stocks, brokers


def reconstruct_record(tx_array: list, stocks: dict, brokers: dict) -> Dict[str, Any]:
    """
    Reconstruct a full floor sheet record from optimized array format.
    
    Args:
        tx_array: [contractId, stockId, buyer, seller, qty, rate, amount, time]
        stocks: Stock lookup dict {stockId: {symbol, name}}
        brokers: Broker lookup dict {memberId: name}
    
    Returns:
        Full record with all fields
    """
    contract_id, stock_id, buyer_id, seller_id, qty, rate, amount, time = tx_array
    
    stock_info = stocks.get(str(stock_id), {})
    
    # Handle null/zero broker IDs (market open session or API change)
    if buyer_id and buyer_id != 0:
        buyer_name = brokers.get(str(buyer_id), f"Broker {buyer_id}")
    else:
        buyer_name = None
    
    if seller_id and seller_id != 0:
        seller_name = brokers.get(str(seller_id), f"Broker {seller_id}")
    else:
        seller_name = None
    
    return {
        "contractId": contract_id,
        "stockId": stock_id,
        "stockSymbol": stock_info.get('symbol', ''),
        "securityName": stock_info.get('name', ''),
        "buyerMemberId": str(buyer_id) if buyer_id else None,
        "sellerMemberId": str(seller_id) if seller_id else None,
        "buyerBrokerName": buyer_name,
        "sellerBrokerName": seller_name,
        "contractQuantity": qty,
        "contractRate": rate,
        "contractAmount": amount,
        "tradeTime": time
    }


def reconstruct_all_records(date_str: str, data_dir: str = None) -> List[Dict[str, Any]]:
    """
    Reconstruct all floor sheet records for a specific date.
    
    Args:
        date_str: Date in YYYY-MM-DD format
        data_dir: Path to data directory
    
    Returns:
        List of full records
    """
    sheet = load_floor_sheet(date_str, data_dir)
    if not sheet:
        return []
    
    stocks, brokers = load_lookups(data_dir)
    
    return [reconstruct_record(tx, stocks, brokers) for tx in sheet['transactions']]


def get_floor_sheet_summary(date_str: str, data_dir: str = None) -> Dict[str, Any]:
    """
    Get summary statistics for a floor sheet.
    
    Returns:
        Dict with date, totalAmount, totalQty, totalTrades, hasBrokerIds
    """
    sheet = load_floor_sheet(date_str, data_dir)
    if not sheet:
        return None
    
    # Check if broker IDs are available
    has_broker_ids = False
    if 'transactions' in sheet and sheet['transactions']:
        # Check first 10 transactions for broker IDs
        has_broker_ids = any(tx[2] != 0 for tx in sheet['transactions'][:10])
    
    return {
        "date": sheet['date'],
        "totalAmount": sheet['totalAmount'],
        "totalQty": sheet['totalQty'],
        "totalTrades": sheet['totalTrades'],
        "hasBrokerIds": has_broker_ids
    }


def list_available_dates(data_dir: str = None) -> List[str]:
    """
    List all available dates in the floor sheet data.
    
    Returns:
        List of date strings in YYYY-MM-DD format
    """
    if data_dir is None:
        data_dir = os.path.join(os.path.dirname(__file__), '..', 'data')
    
    manifest_path = os.path.join(data_dir, 'floor_sheet', 'manifest.json')
    
    if not os.path.exists(manifest_path):
        return []
    
    with open(manifest_path, 'r', encoding='utf-8') as f:
        manifest = json.load(f)
    
    return manifest.get('availableDates', [])


# Example usage
if __name__ == '__main__':
    # List available dates
    dates = list_available_dates()
    print(f"Available dates: {len(dates)}")
    if dates:
        print(f"Latest: {dates[-1]}")
        
        # Get summary
        summary = get_floor_sheet_summary(dates[-1])
        if summary:
            print(f"\nSummary for {summary['date']}:")
            print(f"  Total Trades: {summary['totalTrades']:,}")
            print(f"  Total Quantity: {summary['totalQty']:,}")
            print(f"  Total Amount: Rs. {summary['totalAmount']:,.2f}")
        
        # Reconstruct first 5 records
        records = reconstruct_all_records(dates[-1])
        if records:
            print(f"\nFirst 5 records:")
            for i, rec in enumerate(records[:5], 1):
                print(f"  {i}. {rec['stockSymbol']} | {rec['buyerBrokerName']} -> {rec['sellerBrokerName']} | Qty: {rec['contractQuantity']} @ Rs. {rec['contractRate']}")
