"use client";

import { useEffect, useRef } from "react";

export function ClickBall() {
  const ballRef = useRef<HTMLSpanElement>(null);

  useEffect(() => {
    const ball = ballRef.current;
    if (!ball) return;

    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)");
    let bounce: Animation | undefined;
    const stop = () => bounce?.cancel();

    const playBall = (event: MouseEvent) => {
      if (reduce.matches || !event.detail) return;
      stop();
      ball.style.left = `${event.clientX}px`;
      ball.style.top = `${event.clientY}px`;
      bounce = ball.animate([
        { transform: "translate(-50%, -50%)", opacity: 1 },
        { transform: "translate(2px, 14px) scaleY(.86)", opacity: 1, offset: 0.3 },
        { transform: "translate(12px, -19px)", opacity: 0.95, offset: 0.65 },
        { transform: "translate(22px, 7px) scale(.8)", opacity: 0 },
      ], { duration: 620, easing: "ease-out" });
    };

    document.addEventListener("click", playBall, true);
    reduce.addEventListener("change", stop);
    return () => {
      document.removeEventListener("click", playBall, true);
      reduce.removeEventListener("change", stop);
      stop();
    };
  }, []);

  return <span ref={ballRef} className="click-ball" aria-hidden />;
}
