class Strategy:
    def decide(self, market_data_point, current_capital):
        raise NotImplementedError

    def update_portfolio(self, market_id, side, quantity, price):
        pass
