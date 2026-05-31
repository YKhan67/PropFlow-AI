import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.app.services.risk_engine import RiskManager

def test_risk_manager_comprehensive():
    config = {
        'max_daily_drawdown': 0.05,
        'max_total_drawdown': 0.10,
        'max_position_size': 1.0,
        'account_balance': 100000.0,
        'scale_down_excess': True
    }
    rm = RiskManager(config)

    # 1. Test basic order pass
    order = {'symbol': 'EURUSD', 'volume': 0.1, 'type': 0}
    status, validated = rm.check_order(order)
    assert status == 'approved'
    assert validated['volume'] == 0.1

    # 2. Test max volume modification (scale down)
    order_large = {'symbol': 'EURUSD', 'volume': 2.0, 'type': 0}
    status, validated = rm.check_order(order_large)
    assert status == 'modified'
    assert validated['volume'] == 1.0

    # 3. Test daily drawdown block
    rm.update_equity(94000.0) # 6% drawdown
    status, validated = rm.check_order(order)
    assert status == 'rejected'
    assert validated is None
    
    # 4. Test total drawdown block
    rm.update_equity(100000.0) # Reset to balance
    rm.update_equity(110000.0) # New HWM
    rm.update_equity(98000.0)  # (110 - 98)/110 = 10.9% drawdown
    status, validated = rm.check_order(order)
    assert status == 'rejected'

    # 5. Test rejection when scale_down is False
    config_no_scale = config.copy()
    config_no_scale['scale_down_excess'] = False
    rm2 = RiskManager(config_no_scale)
    status, validated = rm2.check_order(order_large)
    assert status == 'rejected'

    print("All Comprehensive Risk Manager tests passed!")

if __name__ == "__main__":
    test_risk_manager_comprehensive()
