import React, { useEffect, useState } from "react";

type QuotePanelProps = { productId: string; qty: number; unitCents: number };

export function QuotePanel({ productId, qty, unitCents }: QuotePanelProps) {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [shippingCents, setShippingCents] = useState(0);
  const [taxCents, setTaxCents] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    fetch(`/api/quotes?productId=${productId}&qty=${qty}`)
      .then(async (res) => {
        if (!res.ok) throw new Error("quote_failed");
        return res.json();
      })
      .then((data) => {
        if (cancelled) return;
        setShippingCents(Number(data.shippingCents || 0));
        setTaxCents(Number(data.taxCents || 0));
        setLoading(false);
      })
      .catch(() => {
        if (cancelled) return;
        setError("We could not refresh shipping and tax.");
        setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [productId, qty]);

  const goods = unitCents * qty;
  const payable = goods + shippingCents + taxCents;

  if (loading) return <p>Updating quote…</p>;
  if (error) return <p role="alert">{error}</p>;

  return (
    <section>
      <p>Goods: {goods}</p>
      <p>Shipping: {shippingCents}</p>
      <p>Tax: {taxCents}</p>
      <strong>Payable: {payable}</strong>
    </section>
  );
}
