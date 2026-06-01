import logging
import datetime

class RiskManager:
    def __init__(self, config):
        """
        config: dict containing risk parameters:
        - max_daily_drawdown (float): e.g., 0.05 for 5%
        - max_total_drawdown (float): e.g., 0.10 for 10%
        - max_position_size (float): e.g., 0.5 lots
        - account_balance (float): initial balance
        - scale_down_excess (bool): if True, modifies order volume to max allowed instead of rejecting.
        """
        self.config = config
        self.starting_balance = config.get('account_balance', 100000.0)
        self.scale_down_excess = config.get('scale_down_excess', False)
        
        # High Water Marks
        self.hwm_total = self.starting_balance
        self.hwm_daily = self.starting_balance
        self.last_reset_date = datetime.date.today()
        
        # Current status
        self.current_equity = self.starting_balance
        
        logging.info(f"Risk Manager initialized. Starting Balance: {self.starting_balance}")

    def update_equity(self, equity):
        """
        Update the current equity (including unrealized PnL) and recalculate High Water Marks.
        """
        self.current_equity = equity
        
        # Check for daily reset
        today = datetime.date.today()
        if today > self.last_reset_date:
            logging.info(f"Daily reset of Risk Manager. Old Daily HWM: {self.hwm_daily}, New Daily HWM: {self.current_equity}")
            self.hwm_daily = self.current_equity
            self.last_reset_date = today
            
        # Update Total High Water Mark
        if self.current_equity > self.hwm_total:
            self.hwm_total = self.current_equity
            
        # Update Daily High Water Mark
        if self.current_equity > self.hwm_daily:
            self.hwm_daily = self.current_equity

    @property
    def current_total_drawdown(self):
        return (self.hwm_total - self.current_equity) / self.hwm_total

    @property
    def current_daily_drawdown(self):
        return (self.hwm_daily - self.current_equity) / self.hwm_daily

    def check_order(self, order_request, active_trades_count=0):
        """
        The final gate for all orders.
        """
        # 1. Max Active Trades Check
        max_trades = self.config.get('max_active_trades', 5)
        if active_trades_count >= max_trades:
            logging.warning(f"Risk Reject: Max active trades limit reached ({max_trades})")
            return 'rejected', None

        # 2. Drawdown Checks
        max_daily_dd = self.config.get('max_daily_drawdown', 0.05)
        if self.current_daily_drawdown >= max_daily_dd:
            logging.error(f"Risk Reject: Daily drawdown limit reached ({self.current_daily_drawdown:.2%})")
            return 'rejected', None

        max_total_dd = self.config.get('max_total_drawdown', 0.10)
        if self.current_total_drawdown >= max_total_dd:
            logging.error(f"Risk Reject: Total drawdown limit reached ({self.current_total_drawdown:.2%})")
            return 'rejected', None

        # 2. Max Position Size Check
        max_pos = self.config.get('max_position_size', 1.0)
        if order_request['volume'] > max_pos:
            if self.scale_down_excess:
                logging.warning(f"Risk Modify: Scaling down volume from {order_request['volume']} to {max_pos}")
                modified_order = order_request.copy()
                modified_order['volume'] = max_pos
                return 'modified', modified_order
            else:
                logging.warning(f"Risk Reject: Order volume {order_request['volume']} exceeds max {max_pos}")
                return 'rejected', None

        # 3. All checks passed
        logging.info(f"Risk Pass: Order for {order_request['symbol']} approved.")
        return 'approved', order_request

    def get_status(self):
        return {
            "equity": self.current_equity,
            "daily_drawdown": self.current_daily_drawdown,
            "total_drawdown": self.current_total_drawdown,
            "hwm_daily": self.hwm_daily,
            "hwm_total": self.hwm_total
        }
