/** What each figure means and how to use it. */
export function HowItWorks() {
  const steps = [
    ["01", "Del jugador a la estimación", "xValue combina rendimiento, perfil y contexto del jugador para estimar el importe de un traspaso a un club y en una temporada concretos."],
    ["02", "Rango xValue", "La estimación se presenta entre un valor inferior y uno superior. Este rango sirve como referencia para explorar distintos precios."],
    ["03", "Valor de mercado", "Es la valoración de mercado disponible del jugador. La mostramos junto al rango xValue para facilitar la comparación."],
    ["04", "xValue Gap", "Es la diferencia entre la estimación central de xValue y el valor de mercado. Indica cuánto queda por encima o por debajo."],
    ["05", "Explora tus opciones", "En Comprar, sitúa un precio frente al rango. En Vender, compara una oferta con lo pagado. En Comparar, consulta dos jugadores en la misma escala."],
  ] as const;
  return <section className="neural-methodology" aria-label="Cómo funciona xValue">
    <div className="neural-method-flow" data-neural="how-flow" aria-label="xValue Gap igual a estimación central de xValue menos valor de mercado">
      <span>ESTIMACIÓN CENTRAL xVALUE</span><i aria-hidden="true">−</i><span>VALOR DE MERCADO</span><i aria-hidden="true">=</i><strong>xValue Gap</strong>
    </div>
    <div className="neural-method-grid">{steps.map(([number, title, description], index) => <article key={number} data-neural={`how-${index}`}><span>{number}</span><h2>{title}</h2><p>{description}</p></article>)}</div>
  </section>;
}
