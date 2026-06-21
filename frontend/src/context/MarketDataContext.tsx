"use client";

import React, { createContext, useContext, useState, useEffect, useCallback } from "react";

const BACKEND_URL = "http://127.0.0.1:8000";

interface MarketDataContextType {
  symbol: string;
  setSymbol: (sym: string) => void;
  
  // Expiries
  selectedExpiry: string | null;
  setSelectedExpiry: (expiry: string | null) => void;
  expiryList: string[];
  expiryLoading: boolean;

  // Dates selection
  selectedDate: string | null;
  setSelectedDate: (date: string | null) => void;
  marketDatesList: string[];
  marketDatesLoading: boolean;
  
  // Option Chain
  chainData: any | null;
  chainLoading: boolean;
  chainError: string | null;
  
  // Insights
  insightsData: any[];
  insightsLoading: boolean;
  insightsError: string | null;
  
  // Quant Console / Analytics
  quantData: any | null;
  quantLoading: boolean;
  quantError: string | null;

  // Historical Trends
  trendsData: any[] | null;
  trendsLoading: boolean;
  trendsError: string | null;
  
  // General status
  isRefreshing: boolean;
  lastSync: Date | null;
  connected: boolean;
  
  refreshAll: () => Promise<void>;
}

const MarketDataContext = createContext<MarketDataContextType | undefined>(undefined);

const isISTMarketOpen = () => {
  const now = new Date();
  const utc = now.getTime() + now.getTimezoneOffset() * 60000;
  const ist = new Date(utc + 3600000 * 5.5);
  
  const day = ist.getDay(); // 0 = Sunday, 1 = Monday, ..., 6 = Saturday
  if (day === 0 || day === 6) return false;
  
  const hours = ist.getHours();
  const minutes = ist.getMinutes();
  const timeNum = hours * 100 + minutes;
  
  return timeNum >= 915 && timeNum <= 1530;
};

export function MarketDataProvider({ children }: { children: React.ReactNode }) {
  const [symbol, setSymbol] = useState("NIFTY");
  
  const [selectedExpiry, setSelectedExpiry] = useState<string | null>(null);
  const [expiryList, setExpiryList] = useState<string[]>([]);
  const [expiryLoading, setExpiryLoading] = useState(false);

  // Dates selection state
  const [selectedDate, setSelectedDate] = useState<string | null>(null);
  const [marketDatesList, setMarketDatesList] = useState<string[]>([]);
  const [marketDatesLoading, setMarketDatesLoading] = useState(false);
  
  const [chainData, setChainData] = useState<any | null>(null);
  const [chainLoading, setChainLoading] = useState(true);
  const [chainError, setChainError] = useState<string | null>(null);
  
  const [insightsData, setInsightsData] = useState<any[]>([]);
  const [insightsLoading, setInsightsLoading] = useState(true);
  const [insightsError, setInsightsError] = useState<string | null>(null);
  
  const [quantData, setQuantData] = useState<any | null>(null);
  const [quantLoading, setQuantLoading] = useState(true);
  const [quantError, setQuantError] = useState<string | null>(null);

  const [trendsData, setTrendsData] = useState<any[] | null>(null);
  const [trendsLoading, setTrendsLoading] = useState(true);
  const [trendsError, setTrendsError] = useState<string | null>(null);
  
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [lastSync, setLastSync] = useState<Date | null>(null);
  const [connected, setConnected] = useState(false);

  const fetchMarketDates = useCallback(async (sym: string) => {
    setMarketDatesLoading(true);
    try {
      const res = await fetch(`${BACKEND_URL}/api/market-dates?symbol=${sym}`);
      if (!res.ok) throw new Error("Failed to load market dates list");
      const d = await res.json();
      setMarketDatesList(d);
      return d as string[];
    } catch (err) {
      console.error(err);
      return [] as string[];
    } finally {
      setMarketDatesLoading(false);
    }
  }, []);

  const fetchExpiries = useCallback(async (sym: string, date: string | null) => {
    setExpiryLoading(true);
    try {
      const url = date 
        ? `${BACKEND_URL}/api/expiries?symbol=${sym}&date=${date}`
        : `${BACKEND_URL}/api/expiries?symbol=${sym}`;
      const res = await fetch(url);
      if (!res.ok) throw new Error("Failed to load expiries list");
      const d = await res.json();
      setExpiryList(d);
      return d as string[];
    } catch (err) {
      console.error(err);
      return [] as string[];
    } finally {
      setExpiryLoading(false);
    }
  }, []);

  const fetchChain = useCallback(async (sym: string, expiry: string | null, date: string | null, isSilent = false) => {
    if (!isSilent) setChainLoading(true);
    try {
      let url = `${BACKEND_URL}/api/option-chain?symbol=${sym}`;
      if (expiry) url += `&expiry=${expiry}`;
      if (date) url += `&date=${date}`;
      
      const res = await fetch(url);
      if (!res.ok) throw new Error(res.statusText || "Failed to load option chain");
      const d = await res.json();
      setChainData(d);
      setChainError(null);
      return true;
    } catch (err: any) {
      setChainError(err.message || "Connection refused to backend");
      return false;
    } finally {
      setChainLoading(false);
    }
  }, []);

  const fetchInsights = useCallback(async (sym: string, expiry: string | null, date: string | null, isSilent = false) => {
    if (!isSilent) setInsightsLoading(true);
    try {
      let url = `${BACKEND_URL}/api/insights?symbol=${sym}&limit=200`;
      if (expiry) url += `&expiry=${expiry}`;
      if (date) url += `&date=${date}`;
      
      const res = await fetch(url);
      if (!res.ok) throw new Error(res.statusText || "Failed to load insights");
      const d = await res.json();
      setInsightsData(d);
      setInsightsError(null);
    } catch (err: any) {
      setInsightsError(err.message || "Connection refused to backend");
    } finally {
      setInsightsLoading(false);
    }
  }, []);

  const fetchQuant = useCallback(async (sym: string, expiry: string | null, date: string | null, isSilent = false) => {
    if (!isSilent) setQuantLoading(true);
    try {
      let url = `${BACKEND_URL}/api/quant-console?symbol=${sym}`;
      if (expiry) url += `&expiry=${expiry}`;
      if (date) url += `&date=${date}`;
      
      const res = await fetch(url);
      if (!res.ok) {
        if (res.status === 403) throw new Error("Quant Console only accessible in DEV mode.");
        throw new Error(res.statusText || "Failed to load quant console");
      }
      const d = await res.json();
      setQuantData(d);
      setQuantError(null);
    } catch (err: any) {
      setQuantError(err.message || "Connection refused to backend");
    } finally {
      setQuantLoading(false);
    }
  }, []);

  const fetchTrends = useCallback(async (sym: string, expiry: string | null, date: string | null, isSilent = false) => {
    if (!isSilent) setTrendsLoading(true);
    try {
      let url = `${BACKEND_URL}/api/historical-trends?symbol=${sym}`;
      if (expiry) url += `&expiry=${expiry}`;
      if (date) url += `&date=${date}`;
      
      const res = await fetch(url);
      if (!res.ok) throw new Error("Failed to load historical trends");
      const d = await res.json();
      setTrendsData(d.trends || []);
      setTrendsError(null);
    } catch (err: any) {
      setTrendsError(err.message || "Connection refused to backend");
    } finally {
      setTrendsLoading(false);
    }
  }, []);

  const fetchAll = useCallback(async (sym: string, expiry: string | null, date: string | null, isSilent = false) => {
    if (isSilent) {
      setIsRefreshing(true);
    }
    
    const results = await Promise.all([
      fetchChain(sym, expiry, date, isSilent),
      fetchInsights(sym, expiry, date, isSilent),
      fetchQuant(sym, expiry, date, isSilent),
      fetchTrends(sym, expiry, date, isSilent)
    ]);
    
    const chainSuccess = results[0];
    setConnected(chainSuccess);
    if (chainSuccess) {
      setLastSync(new Date());
    }
    setIsRefreshing(false);
  }, [fetchChain, fetchInsights, fetchQuant, fetchTrends]);

  const refreshAll = useCallback(async () => {
    setIsRefreshing(true);
    await fetchAll(symbol, selectedExpiry, selectedDate, true);
    setIsRefreshing(false);
  }, [symbol, selectedExpiry, selectedDate, fetchAll]);

  // Step 1: On symbol change, load dates first, then default to the latest date
  useEffect(() => {
    async function loadDates() {
      const dates = await fetchMarketDates(symbol);
      if (dates.length > 0) {
        if (!selectedDate || !dates.includes(selectedDate)) {
          setSelectedDate(dates[0]); // default to latest
        }
      } else {
        setSelectedDate(null);
        setExpiryList([]);
        setSelectedExpiry(null);
        setChainData(null);
        setChainLoading(false);
        setInsightsLoading(false);
        setQuantLoading(false);
        setTrendsLoading(false);
      }
    }
    loadDates();
  }, [symbol, fetchMarketDates]);

  // Step 2: On date change (or symbol change), load the corresponding expiries
  useEffect(() => {
    async function loadExpiries() {
      if (!selectedDate) {
        setChainLoading(false);
        setInsightsLoading(false);
        setQuantLoading(false);
        setTrendsLoading(false);
        return;
      }
      
      setExpiryLoading(true);
      const expiries = await fetchExpiries(symbol, selectedDate);
      if (expiries.length > 0) {
        if (!selectedExpiry || !expiries.includes(selectedExpiry)) {
          setSelectedExpiry(expiries[0]);
        } else {
          // If the expiry is still valid, trigger full fetch
          fetchAll(symbol, selectedExpiry, selectedDate, false);
        }
      } else {
        setSelectedExpiry(null);
        setChainData(null);
        setChainLoading(false);
        setInsightsLoading(false);
        setQuantLoading(false);
        setTrendsLoading(false);
      }
    }
    loadExpiries();
  }, [selectedDate, symbol, fetchExpiries]);

  // Step 3: On expiry change, trigger full fetch
  useEffect(() => {
    if (selectedExpiry && selectedDate) {
      fetchAll(symbol, selectedExpiry, selectedDate, false);
    }
  }, [selectedExpiry, selectedDate, symbol, fetchAll]);

  // Step 4: 5-minute background refresh (only during market hours)
  useEffect(() => {
    const t = setInterval(() => {
      if (isISTMarketOpen()) {
        fetchAll(symbol, selectedExpiry, selectedDate, true);
      }
    }, 300000);
    
    return () => clearInterval(t);
  }, [symbol, selectedExpiry, selectedDate, fetchAll]);

  return (
    <MarketDataContext.Provider
      value={{
        symbol,
        setSymbol,
        selectedExpiry,
        setSelectedExpiry,
        expiryList,
        expiryLoading,
        selectedDate,
        setSelectedDate,
        marketDatesList,
        marketDatesLoading,
        chainData,
        chainLoading,
        chainError,
        insightsData,
        insightsLoading,
        insightsError,
        quantData,
        quantLoading,
        quantError,
        trendsData,
        trendsLoading,
        trendsError,
        isRefreshing,
        lastSync,
        connected,
        refreshAll
      }}
    >
      {children}
    </MarketDataContext.Provider>
  );
}

export function useMarketData() {
  const context = useContext(MarketDataContext);
  if (!context) {
    throw new Error("useMarketData must be used within a MarketDataProvider");
  }
  return context;
}
