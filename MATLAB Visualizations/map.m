readAPIKey = '{read_api_key}'; 
writeAPIKey = '{write_api_key}';

channelID = {channel_id}; 

distianceFieldID = {total_distance_field_id);

homeLat = 51.5505;
homeLng = -0.4048;

data = thingSpeakRead(channelID, 'ReadKey', readAPIKey, 'Fields', [distianceFieldID], 'NumPoints', 200);

totalDistance = max(data);

earthRadius = 6371008;
lat1 = deg2rad(homeLat);
lng1 = deg2rad(homeLng);

angles = deg2rad([0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100, 110, 120, 130, 140, 150, 160, 170, 180, 190, 200, 210, 220, 230, 240, 250, 260, 270, 280, 290, 300, 310, 320, 330, 340, 350, 360]);

lat2 = asin(sin(lat1) * cos(totalDistance / earthRadius) + cos(lat1) * sin(totalDistance / earthRadius) * cos(angles));
lng2 = lng1 + atan2(sin(angles) * sin(totalDistance/earthRadius) * cos(lat1), cos(totalDistance / earthRadius) - sin(lat1) * sin(lat2));

lat2 = [lat2, lat1];
lng2 = [lng2, lng1];

geobubble(rad2deg(lat2), rad2deg(lng2), 'MapLayout', 'maximized');
geobasemap('topographic');"