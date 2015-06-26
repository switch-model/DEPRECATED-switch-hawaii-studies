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
  double CutInSpeed;     // last speed that has Zero power
  double MaxPowerSpeed;	 // in adjusted speed terms
  double CutOutSpeed;	 // absolute speed
  double MaxPower;       // maximum power
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

//Class 1(C89) Polynomial : y = 0.02224750x6 - 1.09345169x5 + 20.83971017x4 - 197.90345533x3 + 1019.48583138x2 - 2639.91725016x + 2652.67545748 ; R² = 0.99993642
//Class 2(C93) Polynomial : y = 0.04039445x6 - 1.95187354x5 + 36.95840140x4 - 351.40010898x3 + 1800.73609002x2 - 4640.01367349x + 4658.81283912 ; R² = 0.99990693
//Class 3(C96) Polynomial : y = 0.03969050x6 - 1.87439331x5 + 34.56233200x4 - 318.97489466x3 + 1586.05857456x2 - 3951.86900568x + 3824.01454830 ; R² = 0.99992519
//Class 4(C99) Polynomial : y = 0.04902650x6 - 2.26174643x5 + 40.84684710x4 - 370.17366979x3 + 1808.94586408x2 - 4435.86553454x + 4230.86822414 ; R² = 0.99992687

const curvedef curvedefs[] = {
  {3.0, 14.5, 25.0, 2500.0, 2652.67545748, -2639.91725016, 1019.48583138, -197.90345533, 20.839710171, -1.09345169, 0.02224750}, // class I - C89
  {3.0, 13.5, 25.0, 2500.0, 4658.81283912, -4640.01367349, 1800.73609002, -351.40010898, 36.95840140, -1.95187354, 0.04039445}, // class II - C93
  {3.0, 13.5, 25.0, 2500.0, 3824.01454830, -3951.86900568, 1586.05857456, -318.97489466, 34.56233200, -1.87439331, 0.03969050}, // class III - C96
  {3.0, 13.0, 25.0, 2500.0, 4230.86822414, -4435.86553454, 1808.94586408, -370.17366979, 40.84684710, -2.26174643, 0.04902650}, // class IV - C99
};

PG_FUNCTION_INFO_V1(WindPower);

Datum WindPower(PG_FUNCTION_ARGS)
{
  // windclass is the Turbine Wind Class i.e 1(I) , 2(II), 3(III), 4(IV)
  // v is mean wind speed (provided)
  // h is the height of the turbine above sea level (m) i.e Site Elevation + Tower Height
  // T1 is the temperature at the turbine location (degrees Kelvin)
  // T is the temperature at the turbine location (degrees C)

  int32 windclass = PG_GETARG_INT32(0);
  float8 v = PG_GETARG_FLOAT8(1);
  float8 h = PG_GETARG_FLOAT8(2);
  float8 T1 = PG_GETARG_FLOAT8(3);

  float8 densityratio, speedratio;	// adjustment factors for elevation and temperature
  float8 vadj;						// wind speed adjusted for density
  //float8 c;						// Weibull scale factor (calculated)
  //float8 x0, x1, x2;				// range boundaries for Gamma and probability functions
  float8 power;						// average power generated
  float8 T;
  T = T1 - 273.15;       			// Convert T1 from Kelvin to Celcius

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
  //return power;
  PG_RETURN_FLOAT8(power);
}
