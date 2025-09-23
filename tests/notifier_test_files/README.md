Test cases (PGE):

Notifications you should see:

8859 - new notifiable normal outage: in current file, not in previous file
8975 - new notifiable large outage: in current file, not in previous file
9112 - resolved outage: not in current file, in previous file
9119 - escalated small > 4 hours to > 100 > 4 hours
9142 - escalated normal to large < 4 hours 
9178 - escalated large to large > 4 hours

Outages you should not see notifications for:

9217 - large to large < 4 hours 
9233 - normal > 4 hours to large > 4 hours 
9234 - notifiable like 8859, but outside of bay area 
9235 - normal outage that doesn't meet the etor threshold 
9236 - outage that doesn't meet the size threshold 
9237 - normal outage that doesn't meet the elapsed time threshold 

current file:
outage_id  customers_impacted  expected_length_minutes  elapsed_time_minutes
8859                 100                      500                   100
8975                1000                       50                   100
9119                 100                      500                   100
9142                1000                      500                   100
9178                1000                      500                   100
9217                2000                       50                    10
9233                   1                      500                    10
9235                 100                       50                   100
9236                  99                      500                   100
9237                 100                      500                    10

previous file:
outage_id  customers_impacted  expected_length_minutes  elapsed_time_minutes
9112                 160                      500                   100
9119                   2                      500                   100
9142                 100                      500                   100
9178                1000                       50                   100
9217                1000                       50                    10
9233                 999                      500                    10