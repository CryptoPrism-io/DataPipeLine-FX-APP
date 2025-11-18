/**
 * FX Data Pipeline WebSocket Client Example
 *
 * A comprehensive example demonstrating:
 * - Connection and disconnection handling
 * - Subscribing to price updates
 * - Handling alerts
 * - Server statistics
 * - Error handling
 *
 * Usage:
 *   1. Install socket.io-client: npm install socket.io-client
 *   2. Ensure WebSocket server is running: python api/websocket_server.py
 *   3. Run this example: node websocket_client_example.js
 */

const io = require("socket.io-client");

class FXDataPipelineClient {
  constructor(serverUrl = "http://localhost:5001") {
    this.serverUrl = serverUrl;
    this.socket = null;
    this.subscriptions = new Set();
    this.prices = {};
    this.alerts = [];
    this.isConnected = false;
  }

  /**
   * Connect to WebSocket server
   */
  connect() {
    console.log(`\n🔌 Connecting to ${this.serverUrl}...`);

    this.socket = io(this.serverUrl, {
      reconnection: true,
      reconnectionDelay: 1000,
      reconnectionDelayMax: 5000,
      reconnectionAttempts: 5,
    });

    this.socket.on("connect", () => this.onConnect());
    this.socket.on("connection_established", (data) =>
      this.onConnectionEstablished(data)
    );
    this.socket.on("subscription_confirmed", (data) =>
      this.onSubscriptionConfirmed(data)
    );
    this.socket.on("price_update", (data) => this.onPriceUpdate(data));
    this.socket.on("volatility_alert", (data) =>
      this.onVolatilityAlert(data)
    );
    this.socket.on("correlation_alert", (data) =>
      this.onCorrelationAlert(data)
    );
    this.socket.on("data_ready", (data) => this.onDataReady(data));
    this.socket.on("subscriptions_info", (data) =>
      this.onSubscriptionsInfo(data)
    );
    this.socket.on("server_stats", (data) => this.onServerStats(data));
    this.socket.on("price_response", (data) => this.onPriceResponse(data));
    this.socket.on("all_prices_response", (data) =>
      this.onAllPricesResponse(data)
    );
    this.socket.on("subscription_error", (data) =>
      this.onSubscriptionError(data)
    );
    this.socket.on("price_error", (data) => this.onPriceError(data));
    this.socket.on("server_error", (data) => this.onServerError(data));
    this.socket.on("pong", (data) => this.onPong(data));
    this.socket.on("disconnect", () => this.onDisconnect());
    this.socket.on("error", (error) => this.onError(error));
  }

  // ========== CONNECTION HANDLERS ==========

  onConnect() {
    console.log("✅ Connected to WebSocket server");
    this.isConnected = true;
  }

  onConnectionEstablished(data) {
    console.log(`\n📡 Connection Established:`);
    console.log(`   Client ID: ${data.client_id}`);
    console.log(`   Tracked Pairs: ${data.pair_count}`);
    console.log(`   Active Clients: ${data.active_clients}/${data.max_clients}`);
  }

  onDisconnect() {
    console.log("\n🔴 Disconnected from WebSocket server");
    this.isConnected = false;
  }

  onError(error) {
    console.error("\n❌ Socket Error:", error);
  }

  // ========== SUBSCRIPTION HANDLERS ==========

  onSubscriptionConfirmed(data) {
    data.pairs.forEach((pair) => this.subscriptions.add(pair));
    console.log(
      `\n✅ Subscription Confirmed: ${data.pair_count} pairs (Total: ${this.subscriptions.size})`
    );
    console.log(`   Pairs: ${data.pairs.join(", ")}`);
  }

  onSubscriptionsInfo(data) {
    console.log(`\n📋 Current Subscriptions:`);
    console.log(`   Count: ${data.pair_count}`);
    console.log(`   Pairs: ${data.subscribed_pairs.join(", ")}`);
    console.log(`   Subscribed to All: ${data.subscribed_to_all}`);
  }

  // ========== PRICE HANDLERS ==========

  onPriceUpdate(data) {
    this.prices[data.instrument] = data.price;
    const price = data.price;
    console.log(
      `💱 ${data.instrument}: ${price.mid} (Bid: ${price.bid}, Ask: ${price.ask})`
    );
  }

  onPriceResponse(data) {
    const price = data.price;
    console.log(
      `\n💰 Price Request Response:`
    );
    console.log(`   ${data.instrument}: ${price.mid}`);
    console.log(`   Bid: ${price.bid}, Ask: ${price.ask}`);
    console.log(`   Time: ${price.time}`);
  }

  onAllPricesResponse(data) {
    console.log(
      `\n💰 All Prices (${data.pair_count} pairs):`
    );
    for (const [pair, price] of Object.entries(data.prices)) {
      console.log(
        `   ${pair}: ${price.mid} (${price.bid}/${price.ask})`
      );
    }
  }

  onPriceError(data) {
    console.error(`\n❌ Price Error: ${data.error}`);
    if (data.message) {
      console.error(`   ${data.message}`);
    }
  }

  // ========== ALERT HANDLERS ==========

  onVolatilityAlert(data) {
    const icon =
      data.severity === "critical" ? "🚨" : data.severity === "warning" ? "⚠️ " : "ℹ️ ";
    console.log(
      `\n${icon} Volatility Alert: ${data.instrument}`
    );
    console.log(`   Value: ${data.volatility}`);
    console.log(`   Threshold: ${data.threshold}`);
    console.log(`   Severity: ${data.severity}`);
    console.log(`   Message: ${data.message}`);

    this.alerts.push({
      type: "volatility",
      instrument: data.instrument,
      severity: data.severity,
      timestamp: new Date(data.timestamp),
    });
  }

  onCorrelationAlert(data) {
    console.log(
      `\n🔗 Correlation Alert: ${data.pair1} <-> ${data.pair2}`
    );
    console.log(`   Correlation: ${data.correlation}`);
    console.log(`   Threshold: ${data.threshold}`);
    console.log(`   Message: ${data.message}`);

    this.alerts.push({
      type: "correlation",
      pairs: [data.pair1, data.pair2],
      correlation: data.correlation,
      timestamp: new Date(data.timestamp),
    });
  }

  onDataReady(data) {
    console.log(`\n📊 Data Ready: ${data.data_type}`);
    console.log(`   Count: ${data.count}`);
    console.log(`   Message: ${data.message}`);
  }

  onSubscriptionError(data) {
    console.error(`\n❌ Subscription Error: ${data.error}`);
  }

  onServerError(data) {
    console.error(`\n❌ Server Error: ${data.error}`);
  }

  // ========== STATS HANDLERS ==========

  onServerStats(data) {
    console.log(`\n📈 Server Statistics:`);
    console.log(
      `   Active Clients: ${data.active_clients}/${data.max_clients}`
    );
    console.log(`   Total Subscriptions: ${data.total_subscriptions}`);
    console.log(
      `   Avg Subs/Client: ${data.average_subs_per_client.toFixed(2)}`
    );
    if (data.cache && data.cache.memory) {
      console.log(`   Cache Memory: ${data.cache.memory.used_memory}`);
    }
  }

  onPong(data) {
    const latency = Date.now() - this.lastPingTime;
    console.log(`📡 Pong: ${latency}ms`);
  }

  // ========== PUBLIC METHODS ==========

  /**
   * Subscribe to specific pairs or all pairs
   */
  subscribe(pairs) {
    if (!this.isConnected) {
      console.error("❌ Not connected");
      return;
    }

    if (pairs === "all" || pairs === "*") {
      console.log("\n📡 Subscribing to ALL pairs...");
      this.socket.emit("subscribe", { pairs: "*" });
    } else if (Array.isArray(pairs)) {
      console.log(`\n📡 Subscribing to ${pairs.length} pairs...`);
      this.socket.emit("subscribe", { pairs });
    } else {
      console.log(`\n📡 Subscribing to ${pairs}...`);
      this.socket.emit("subscribe", { pairs: [pairs] });
    }
  }

  /**
   * Unsubscribe from specific pairs or all pairs
   */
  unsubscribe(pairs) {
    if (!this.isConnected) {
      console.error("❌ Not connected");
      return;
    }

    if (pairs === "all" || pairs === "*") {
      console.log("\n📡 Unsubscribing from ALL pairs...");
      this.socket.emit("unsubscribe", { pairs: "*" });
    } else if (Array.isArray(pairs)) {
      console.log(`\n📡 Unsubscribing from ${pairs.length} pairs...`);
      this.socket.emit("unsubscribe", { pairs });
    } else {
      console.log(`\n📡 Unsubscribing from ${pairs}...`);
      this.socket.emit("unsubscribe", { pairs: [pairs] });
    }
  }

  /**
   * Get current subscriptions
   */
  getSubscriptions() {
    if (!this.isConnected) {
      console.error("❌ Not connected");
      return;
    }

    console.log("\n📋 Requesting subscriptions info...");
    this.socket.emit("get_subscriptions");
  }

  /**
   * Request current price for a pair
   */
  requestPrice(instrument) {
    if (!this.isConnected) {
      console.error("❌ Not connected");
      return;
    }

    console.log(`\n💰 Requesting price for ${instrument}...`);
    this.socket.emit("request_price", { instrument });
  }

  /**
   * Request all prices
   */
  requestAllPrices() {
    if (!this.isConnected) {
      console.error("❌ Not connected");
      return;
    }

    console.log("\n💰 Requesting all prices...");
    this.socket.emit("request_all_prices");
  }

  /**
   * Get server statistics
   */
  getServerStats() {
    if (!this.isConnected) {
      console.error("❌ Not connected");
      return;
    }

    console.log("\n📈 Requesting server statistics...");
    this.socket.emit("get_server_stats");
  }

  /**
   * Send ping to measure latency
   */
  ping() {
    if (!this.isConnected) {
      console.error("❌ Not connected");
      return;
    }

    this.lastPingTime = Date.now();
    this.socket.emit("ping");
  }

  /**
   * Print current prices
   */
  printPrices() {
    if (Object.keys(this.prices).length === 0) {
      console.log("\n💱 No prices received yet");
      return;
    }

    console.log(`\n💱 Current Prices (${Object.keys(this.prices).length}):`);
    for (const [pair, price] of Object.entries(this.prices)) {
      console.log(
        `   ${pair}: ${price.mid} (B: ${price.bid}, A: ${price.ask})`
      );
    }
  }

  /**
   * Disconnect from server
   */
  disconnect() {
    if (this.socket) {
      console.log("\n🔌 Disconnecting...");
      this.socket.disconnect();
    }
  }
}

// ========== INTERACTIVE EXAMPLE ==========

async function main() {
  const client = new FXDataPipelineClient("http://localhost:5001");

  console.log("\n" + "=".repeat(60));
  console.log(
    "   FX Data Pipeline WebSocket Client Example"
  );
  console.log("=".repeat(60));

  // Connect
  client.connect();

  // Wait for connection
  await new Promise((resolve) => setTimeout(resolve, 2000));

  // Subscribe to specific pairs
  client.subscribe(["EUR_USD", "GBP_USD", "USD_JPY"]);

  // Wait for subscription
  await new Promise((resolve) => setTimeout(resolve, 1000));

  // Request current subscriptions
  client.getSubscriptions();

  // Wait a bit
  await new Promise((resolve) => setTimeout(resolve, 1000));

  // Request current prices
  client.requestPrice("EUR_USD");

  // Wait
  await new Promise((resolve) => setTimeout(resolve, 500));

  // Request all prices
  client.requestAllPrices();

  // Wait
  await new Promise((resolve) => setTimeout(resolve, 500));

  // Get server stats
  client.getServerStats();

  // Set up periodic ping to measure latency
  setInterval(() => {
    client.ping();
  }, 30000);

  // Keep running and listen for events
  console.log("\n✅ Client initialized. Listening for events...");
  console.log(
    "   (The client will automatically receive price updates and alerts)"
  );
  console.log(
    "   (Server will continue until you manually disconnect)"
  );

  // Uncomment to test subscription changes after some time
  /*
  setTimeout(() => {
    console.log("\n--- Switching subscriptions after 10 seconds ---");
    client.unsubscribe(["EUR_USD"]);
    setTimeout(() => {
      client.subscribe(["AUD_USD", "NZD_USD"]);
    }, 500);
  }, 10000);
  */

  // Keep process alive
  setInterval(() => {
    if (client.prices && Object.keys(client.prices).length > 0) {
      // Just keep updating internal state
    }
  }, 60000);
}

// Run if executed directly
if (require.main === module) {
  main().catch(console.error);
}

module.exports = FXDataPipelineClient;
