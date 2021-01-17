% I configure this to run hourly

readAPIKey = '{read_api_key}'; 
writeAPIKey = '{write_api_key}';

channelID = {channel_id}; 

rotationFieldID = {rotation_field_id);
distianceFieldID = {distance_field_id};
rotationFieldID = {daily_rotation_field_id);
distianceFieldID = {daily_distance_field_id);

[data,timestamps] = thingSpeakRead(channelID,'Fields',[rotationFieldID,distianceFieldID],'NumMinutes',720,'ReadKey',readAPIKey);

tStamp = datetime('now');
dailyTotals = sum(data, 'omitnan');

thingSpeakWrite(channelID,[dailyTotals(1),dailyTotals(2)],'Fields',[rotationFieldID,distianceFieldID],'WriteKey',writeAPIKey,'TimeStamp',tStamp);