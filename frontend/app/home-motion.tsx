"use client";

import { useEffect, useRef } from "react";

export function HomeMotion() {
  const ballRef = useRef<HTMLSpanElement>(null);

  useEffect(() => {
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)");
    const observer = "IntersectionObserver" in window ? new IntersectionObserver((entries) => {
      entries.forEach(({ target, isIntersecting }) => {
        if (isIntersecting) {
          target.classList.add("home-entered");
          observer?.unobserve(target);
        }
      });
    }, { threshold: 0.12 }) : undefined;
    document.querySelectorAll("[data-home-enter]").forEach((element) => observer?.observe(element));

    let bounce: Animation | undefined;
    const stop = () => bounce?.cancel();
    function playBall(event: MouseEvent) {
      const ball = ballRef.current;
      if (reduce.matches || !event.detail || !ball || !(event.target instanceof HTMLElement) ||
          !event.target.matches("body, #main-content, [data-ball-space]")) return;
      bounce?.cancel();
      ball.style.left = `${event.clientX}px`;
      ball.style.top = `${event.clientY}px`;
      bounce = ball.animate([
        { transform: "translate(-50%, -50%)", opacity: 1 },
        { transform: "translate(2px, 14px) scaleY(.86)", opacity: 1, offset: 0.3 },
        { transform: "translate(12px, -19px)", opacity: 0.95, offset: 0.65 },
        { transform: "translate(22px, 7px) scale(.8)", opacity: 0 },
      ], { duration: 620, easing: "ease-out" });
    }

    document.addEventListener("click", playBall);
    reduce.addEventListener("change", stop);
    return () => {
      document.removeEventListener("click", playBall);
      reduce.removeEventListener("change", stop);
      observer?.disconnect();
      stop();
    };
  }, []);

  return <span ref={ballRef} className="home-ball" aria-hidden />;
}
