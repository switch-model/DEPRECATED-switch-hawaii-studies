/* based on http://www.postgresql.org/docs/9.3/static/xfunc-c.html

compile with these commands:
cd '/Volumes/Data/DB_Code/WindPower UDF'
cc -I`pg_config --includedir-server` -c WindPower.c
cc -bundle -flat_namespace -undefined suppress -o WindPower.so WindPower.o

 then install with this command:
CREATE FUNCTION WindPower(int, double precision, double precision, double precision) RETURNS double precision
     AS '/Volumes/Data/DB_Code/WindPower UDF/WindPower', 'WindPower'
     LANGUAGE C STRICT;
*/

#include <math.h>
//#include "/Library/PostgreSQL/9.3/include/postgresql/server/postgres.h"
#include "postgres.h"

#include "fmgr.h"

// environmental constants
#define Lapse	0.0065		// decrease in temperature with increase in elevation (deg C/m)
#define Rd		287.053		// gas constant for dry air
#define Gravity	9.807		// gravitational acceleration (m/s^2)

#ifdef PG_MODULE_MAGIC
PG_MODULE_MAGIC;
#endif

typedef struct {
  double CutInSpeed;
  double MaxPowerSpeed;	// in adjusted speed terms
  double CutOutSpeed;	// absolute speed
  double MaxPower;
  // The coefficients for the polynomial form of the power curve.
  // These are found by using a polynomial regression on the curvy part of the curve
  // (ideally including the last 0 at the bottom and first 100% output at the top)
  double V0;
  double V1;
  double V2;
  double V3;
  double V4;
  double V5;
  double V6;
} curvedef;

const curvedef curvedefs[] = {
  {3.20045949389385, 15.0344424204553, 25.0, 2500.0, 1037.382, -1267.6386, 561.9836925, -120.0762565, 13.69171579, -0.756091594, 0.015828643}, // class I - C89
  {2.905615, 14.6245524305755, 25.0, 2500.0, 2282.3012, -2385.4537, 959.2227572, -192.015572, 20.78867729, -1.116560565, 0.023156628}, // class II - C93
  {3.05532, 13.9628281, 25.0, 2500.0, 3128.5525, -3224.4679, 1291.270606, -259.2301679, 28.17382686, -1.530123345, 0.032321862}, // class III - C96
  {2.9807625, 13.46821985, 25.0, 2500.0, 3587.5318, -3778.1170, 1546.878826, -317.1882212, 35.08647035, -1.941256844, 0.041872187}, // class IV - C99
};

double WindPower(int windclass, double v, double h, double T)
{
  // v is mean wind speed (provided)
  // h is the height of the turbine above sea level (m)
  // T is the temperature at the turbine location (degrees C)

  double densityratio, speedratio;	// adjustment factors for elevation and temperature
  double vadj;						// wind speed adjusted for density
  double c;			// Weibull scale factor (calculated)
  double x0, x1, x2;	// range boundaries for Gamma and probability functions
  double power;		// average power generated

  const curvedef *curve;
  if (windclass < 1 || windclass > 4) windclass = 1;
  curve = &(curvedefs[windclass-1]);

  // this accounts for the effect of temperature and altitude on air density, relative to STP
  densityratio=288.15/(T+273.15)*pow(1+(Lapse*h)/(T+273.15), -Gravity/(Rd*Lapse));
  // calculate the change in windspeed that would make STP air have the same power as this air
  speedratio=pow(densityratio, 0.3333333333);

  vadj = v * speedratio;

  if (v < curve->CutInSpeed || v >= curve->CutOutSpeed)
    power = 0;
  else if (vadj >= curve->MaxPowerSpeed)
    power = curve->MaxPower;
  else   // in the polynomial power range
    power = curve->V6*pow(vadj, 6) + curve->V5*pow(vadj, 5) + curve->V4*pow(vadj, 4)
    + curve->V3*pow(vadj, 3) + curve->V2*pow(vadj, 2) + curve->V1*vadj + curve->V0;

  if (power < 0) power = 0;
  if (power > curve->MaxPower) power = curve->MaxPower;
  return power;
}
