"""Deterministic Weather Risk Intelligence Engine.

Computes rule-based, deterministic risk scores and mitigation recommendations
for event planners based on meteorological observations (rainfall, extreme temperature,
wind velocity, and humidity).

This engine runs strictly outside the LLM to guarantee predictable, audited safety logic.
"""

from typing import List, Optional, Tuple

from app.schemas.external_data import (
    NormalizedWeatherMeasurements,
    WeatherRiskAssessment,
    WeatherRiskFactor,
    WeatherRiskLevel,
)

# Configurable Meteorological Thresholds
RAIN_SEVERE_THRESHOLD_MM = 10.0
RAIN_HIGH_THRESHOLD_MM = 3.0
RAIN_MODERATE_THRESHOLD_MM = 0.5

TEMP_SEVERE_HEAT_C = 40.0
TEMP_HIGH_HEAT_C = 35.0
TEMP_MODERATE_HEAT_C = 32.0
TEMP_COLD_C = 12.0

WIND_SEVERE_MPS = 13.0   # ~47 km/h
WIND_HIGH_MPS = 8.5      # ~30 km/h
WIND_MODERATE_MPS = 5.5  # ~20 km/h

HUMIDITY_HIGH_PCT = 80


def evaluate_weather_risks(
    measurements: Optional[NormalizedWeatherMeasurements],
) -> WeatherRiskAssessment:
    """Evaluates weather measurements deterministically and returns structured risk analysis."""
    if not measurements:
        return WeatherRiskAssessment(
            overall_risk=WeatherRiskLevel.LOW,
            is_outdoor_suitable=True,
            risk_score=0,
            factors=[],
            recommendations=[
                "Live weather measurements currently unavailable. Formulate a rainy-day indoor contingency plan as standard practice."
            ],
            disclaimer="No live meteorological measurements available for automated risk evaluation.",
        )

    factors: List[WeatherRiskFactor] = []
    recommendations: List[str] = []
    factor_scores: List[int] = []

    # 1. Rainfall / Precipitation Risk
    rain = measurements.rainfall_mm or 0.0
    cond = (measurements.weather_condition or "").lower()
    is_rain_condition = any(w in cond for w in ("rain", "thunderstorm", "drizzle", "shower", "storm"))

    if rain >= RAIN_SEVERE_THRESHOLD_MM or "thunderstorm" in cond:
        factors.append(
            WeatherRiskFactor(
                name="rainfall",
                level=WeatherRiskLevel.SEVERE,
                value_observed=f"{rain:.1f} mm/hr ({measurements.weather_condition or 'Heavy Rain'})",
                threshold_applied=f">= {RAIN_SEVERE_THRESHOLD_MM} mm/hr or Thunderstorm",
                message="Heavy rainfall or thunderstorm forecast.",
                recommendation="Severe precipitation will disrupt open-air setups. Relocate all critical ceremonies indoors or deploy fully enclosed, water-tight German hangar structures.",
            )
        )
        recommendations.append("Severe rain alert: Mandate indoor venue or heavy-duty water-tight hangar structures.")
        factor_scores.append(85)
    elif rain >= RAIN_HIGH_THRESHOLD_MM or (is_rain_condition and rain > 1.0):
        factors.append(
            WeatherRiskFactor(
                name="rainfall",
                level=WeatherRiskLevel.HIGH,
                value_observed=f"{rain:.1f} mm/hr ({measurements.weather_condition or 'Rain'})",
                threshold_applied=f">= {RAIN_HIGH_THRESHOLD_MM} mm/hr",
                message="Substantial rainfall forecast during event hours.",
                recommendation="High risk of lawn saturation and guest discomfort. Prepare covered walkways, waterproof stage canopies, and hard-floor subsurfaces.",
            )
        )
        recommendations.append("High rain risk: Secure covered stage/dining areas and inspect turf drainage.")
        factor_scores.append(65)
    elif rain >= RAIN_MODERATE_THRESHOLD_MM or is_rain_condition:
        factors.append(
            WeatherRiskFactor(
                name="rainfall",
                level=WeatherRiskLevel.MODERATE,
                value_observed=f"{rain:.1f} mm/hr ({measurements.weather_condition or 'Light Rain'})",
                threshold_applied=f">= {RAIN_MODERATE_THRESHOLD_MM} mm/hr",
                message="Light scattered rain or drizzle observed.",
                recommendation="Keep outdoor umbrellas on standby, protect AV electronic sound gear, and designate a backup indoor hall.",
            )
        )
        recommendations.append("Moderate rain risk: Keep backup indoor space and protect electrical sound equipment.")
        factor_scores.append(35)
    else:
        factor_scores.append(0)

    # 2. Temperature Risk (Extreme Heat or Cold)
    temp = measurements.temperature_c
    feels = measurements.feels_like_c or temp

    if temp is not None:
        if temp >= TEMP_SEVERE_HEAT_C or (feels and feels >= TEMP_SEVERE_HEAT_C):
            factors.append(
                WeatherRiskFactor(
                    name="temperature",
                    level=WeatherRiskLevel.SEVERE,
                    value_observed=f"{temp:.1f}°C (Feels like {feels:.1f}°C)",
                    threshold_applied=f">= {TEMP_SEVERE_HEAT_C}°C",
                    message="Extreme scorching heat condition.",
                    recommendation="Dangerous heat levels. Avoid daytime outdoor ceremonies. Provide industrial air coolers, shaded shamianas, and continuous cold hydration stations.",
                )
            )
            recommendations.append("Extreme heat alert: Schedule outdoors strictly after sunset; provide abundant shade and misting fans.")
            factor_scores.append(80)
        elif temp >= TEMP_HIGH_THRESHOLD_C if "TEMP_HIGH_THRESHOLD_C" in locals() else temp >= TEMP_HIGH_HEAT_C:
            factors.append(
                WeatherRiskFactor(
                    name="temperature",
                    level=WeatherRiskLevel.HIGH,
                    value_observed=f"{temp:.1f}°C (Feels like {feels:.1f}°C)",
                    threshold_applied=f">= {TEMP_HIGH_HEAT_C}°C",
                    message="Elevated daytime temperatures.",
                    recommendation="High ambient heat will cause attendee fatigue. Arrange shaded canopy seating, portable misting fans, and cold welcome beverages.",
                )
            )
            recommendations.append("High heat alert: Provide shaded canopies and active fan cooling.")
            factor_scores.append(50)
        elif temp >= TEMP_MODERATE_HEAT_C:
            factors.append(
                WeatherRiskFactor(
                    name="temperature",
                    level=WeatherRiskLevel.MODERATE,
                    value_observed=f"{temp:.1f}°C",
                    threshold_applied=f">= {TEMP_MODERATE_HEAT_C}°C",
                    message="Warm weather conditions.",
                    recommendation="Ensure well-ventilated outdoor seating and sufficient refreshments.",
                )
            )
            factor_scores.append(20)
        elif temp <= TEMP_COLD_C:
            factors.append(
                WeatherRiskFactor(
                    name="temperature",
                    level=WeatherRiskLevel.MODERATE,
                    value_observed=f"{temp:.1f}°C",
                    threshold_applied=f"<= {TEMP_COLD_C}°C",
                    message="Chilly evening or night temperature.",
                    recommendation="Nighttime chill expected. Arrange patio outdoor heaters or fire bowls and warm beverage counters.",
                )
            )
            recommendations.append("Chilly evening forecast: Arrange outdoor patio heaters or bonfire stations.")
            factor_scores.append(25)
        else:
            factor_scores.append(0)

    # 3. Wind Velocity Risk
    wind = measurements.wind_speed_mps or 0.0
    if wind >= WIND_SEVERE_MPS:
        factors.append(
            WeatherRiskFactor(
                name="wind",
                level=WeatherRiskLevel.SEVERE,
                value_observed=f"{wind:.1f} m/s (~{wind * 3.6:.0f} km/h)",
                threshold_applied=f">= {WIND_SEVERE_MPS} m/s",
                message="Gale or high wind gusts.",
                recommendation="Severe wind hazard. Structural hazard for temporary trussing, sound walls, and high floral arches. Must anchor or dismantle tall outdoor displays.",
            )
        )
        recommendations.append("High wind warning: Heavily counter-weight all trusses and avoid tall freestanding floral arches.")
        factor_scores.append(75)
    elif wind >= WIND_HIGH_MPS:
        factors.append(
            WeatherRiskFactor(
                name="wind",
                level=WeatherRiskLevel.HIGH,
                value_observed=f"{wind:.1f} m/s (~{wind * 3.6:.0f} km/h)",
                threshold_applied=f">= {WIND_HIGH_MPS} m/s",
                message="Brisk wind gusts.",
                recommendation="Secure table linens, affix tent sidewalls, and counter-weight backdrop frames.",
            )
        )
        recommendations.append("Brisk wind alert: Secure tablecloths, lightweight signage, and stage backdrops.")
        factor_scores.append(45)
    elif wind >= WIND_MODERATE_MPS:
        factors.append(
            WeatherRiskFactor(
                name="wind",
                level=WeatherRiskLevel.MODERATE,
                value_observed=f"{wind:.1f} m/s",
                threshold_applied=f">= {WIND_MODERATE_MPS} m/s",
                message="Moderate breeze.",
                recommendation="Use weighted stands for standalone entrance banners.",
            )
        )
        factor_scores.append(15)
    else:
        factor_scores.append(0)

    # 4. Humidity Discomfort
    hum = measurements.humidity_pct or 0
    if hum >= HUMIDITY_HIGH_PCT and (temp is None or temp >= 28.0):
        factors.append(
            WeatherRiskFactor(
                name="humidity",
                level=WeatherRiskLevel.MODERATE,
                value_observed=f"{hum}%",
                threshold_applied=f">= {HUMIDITY_HIGH_PCT}%",
                message="Heavy atmospheric humidity.",
                recommendation="Muggy conditions. Ensure continuous air circulation fans in semi-covered pavilions.",
            )
        )
        factor_scores.append(20)

    # Calculate aggregate risk score (0 - 100)
    aggregate_score = min(100, max(factor_scores) if factor_scores else 0)

    # Determine overall categorical risk level
    if any(f.level == WeatherRiskLevel.SEVERE for f in factors):
        overall_risk = WeatherRiskLevel.SEVERE
    elif any(f.level == WeatherRiskLevel.HIGH for f in factors):
        overall_risk = WeatherRiskLevel.HIGH
    elif any(f.level == WeatherRiskLevel.MODERATE for f in factors):
        overall_risk = WeatherRiskLevel.MODERATE
    else:
        overall_risk = WeatherRiskLevel.LOW

    # Outdoor event suitability check
    is_outdoor_suitable = not (
        overall_risk in (WeatherRiskLevel.SEVERE, WeatherRiskLevel.HIGH)
        or (rain > 1.5)
        or (wind > WIND_HIGH_MPS)
        or (temp is not None and temp >= TEMP_SEVERE_HEAT_C)
    )

    if is_outdoor_suitable and not recommendations:
        recommendations.append("Atmospheric conditions are favorable for open-air lawn ceremonies and outdoor dining.")

    return WeatherRiskAssessment(
        overall_risk=overall_risk,
        is_outdoor_suitable=is_outdoor_suitable,
        risk_score=aggregate_score,
        factors=factors,
        recommendations=recommendations,
    )

