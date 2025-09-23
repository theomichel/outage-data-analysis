Test cases (PGE):

Run this...
py .\outage_notifier.py -d .\tests\notifier_test_files\ -u pge --telegram-token "<token>" --telegram-chat-id "<test_chat_id>" --telegram-thread-id "<test_thread_id>" --geocode-api-key "<test_geocode_api_key>" -zw "./constant_data/bay_area_zip_codes.txt" -zb "./constant_data/ca_california_zip_codes_geo.min.json"

Notifications you should see:

8859 - new notifiable normal outage: in current file, not in previous file
8975 - new notifiable large outage: in current file, not in previous file
9112 - resolved outage: not in current file, in previous file
9119 - escalated small > 4 hours resolution to > 100 > 4 hours resolution
9142 - escalated normal to large < 4 hours resolution
9178 - escalated large close resolution to large > 4 hours resolution
9179 - escalated large no null resolution to large > 4 hours resolution

Outages you should not see notifications for:

9217 - large to large < 4 hours resolution
9233 - normal > 4 hours resolution to large > 4 hours resolution 
9234 - notifiable like 8859, but outside of bay area 
9235 - normal outage that doesn't meet the etor threshold 
9236 - outage that doesn't meet the size threshold 
9237 - normal outage that doesn't meet the elapsed time threshold 

summary of outages in the "current" file (tests\notifier_test_files\2025-08-29T225732-pge-events.json):
outage_id  customers_impacted  expected_length_minutes  elapsed_time_minutes
8859                 100                      500                   100
8975                1000                       50                   100
9119                 100                      500                   100
9142                1000                      500                   100
9178                1000                      500                   100
9178                1000                      500                   100
9217                2000                       50                    10
9233                   1                      500                    10
9235                 100                       50                   100
9236                  99                      500                   100
9237                 100                      500                    10

summary of outages in the "previous" file (tests\notifier_test_files\2025-08-29T224647-pge-events.json):
outage_id  customers_impacted  expected_length_minutes  elapsed_time_minutes
9112                 160                      500                   100
9119                   2                      500                   100
9142                 100                      500                   100
9178                1000                       50                   100
9179                1000                  unknown                   100
9217                1000                       50                    10
9233                 999                      500                    10