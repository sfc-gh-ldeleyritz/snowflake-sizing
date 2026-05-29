<iframe tabindex="-1" aria-hidden="true"></iframe>

<iframe src="https://chat.google.com/u/0/mole/world?wfi=gtn-brain-iframe-id&hs=%5B%22h_hs%22%2Cnull%2Cnull%2C%5B2%2C0%5D%2Cnull%2Cnull%2C%22gmail.pinto-server_20260521.07_p0%22%2Cnull%2Cnull%2C%5B6%2C58%2C17%2C20%2C21%2C1%2C19%2C31%2C84%2C60%2C67%2C106%5D%2Cnull%2Cnull%2C%22pJRTkFQRiig.en.L.es5%22%2Cnull%2Cnull%2Cnull%2Cnull%2Cnull%2C0%5D&hl=en&ilt=9180479541092647913&dip=3&shell=6&has_stream_view=false&origin=https%3A%2F%2Fmail.google.com&oi=1#hot=1779956458003" id="gtn-brain-iframe-id" name="gtn-brain-iframe-id" class="wYWn3" allow="idle-detection; autoplay; clipboard-write; clipboard-read;camera; microphone; cross-origin-isolated; fullscreen;"></iframe>

None selected

[Skip to content](https://mail.google.com/mail/u/0/)
[Using Snowflake Inc. Mail with screen readers](https://mail.google.com/mail/u/0/)

|  |
| - |

|  |
| - |

[]()

<iframe class="ir" id="gtn-roster-iframe-id" name="gtn-roster-iframe-id" tabindex="-1" title="Chat" aria-label="Chat" src="https://chat.google.com/u/0/frame?shell=6&pt=6&origin=https%3A%2F%2Fmail.google.com&oi=1&dip=3#cb=gtn-brain-iframe-id&id=world&pt=6"></iframe>

## Conversations

|  |  |  |  |
| - | - | - | - |
|  |  |  |  |
|  |  |  |  |

[](https://www.google.com/gmail/about/policy/)[](https://www.google.com/)

## Re: Architecture for data warehouse approach

External

Inbox

CUSTOMER

![](https://lh3.googleusercontent.com/a/default-user=s80-p)

| | ### Emanuele Nardo <**insights@apidae.digital**>###  |
| -------------------------------------------------------- |

| Wed, May 27, 9:13 AM (1 day ago)                                                                                   |                                                                                                                                                       |  |  |
| ------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------- | - | - |
|                                                                                                                     | **to** **Josh**, **jonathan**, **Matt**, **me**, **James**![](https://mail.google.com/mail/u/0/images/cleardot.gif) |  |  |
| ------------------------------------------------------------------------------------------------------------------- |                                                                                                                                                       |  |  |

 |

Hi Josh,

this is **Betpanda**'s AWS ID where the Data Lake is stored. 217793907504Should you need anything else, please let me know.Best regards, Emanuele

On Tue, 26 May 2026 at 19:49, Josh Lilien [[josh.lilien@snowflake.com](mailto:josh.lilien@snowflake.com)](%5Bjosh.lilien@snowflake.com%5D(mailto:josh.lilien@snowflake.com)) wrote:

> Thank you Emanuele. We’ll set that up on our end when Matt and Alex are back on Monday!
>
> Looping in James Kinley who is better suited to answer the open flow specific questions!
>
> Also, can you please let us know your AWS ID? There are usually good funding incentives we can take advantage of.
>
> Best,
>
> Josh
>
> | JOSHLILIENAccount Director``MOBILE+44 7826 875 276`` |
> | ----------------------------------------------------------------------- |
>
> | ``![](https://ci3.googleusercontent.com/meips/ADKq_NZTPkwnPcmoWC3Bun64-apwSibVWDW2o-WpPAVuVOWxh7WE8xG4Brj_MAj-VJq4AUYQjDlU1h_ddhm1hxWlD5qQB8WPAn-gVb-rChAlJ5bou64swjwrSfxJl2g4prigEOCoNGvXy_W8HYM=s0-d-e1-ft#https://www.snowflake.com/wp-content/themes/snowflake/img/snowflake-logo-blue@2x.png)`` |
> | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
>
> | Snowflake Inc.``One Crown Place``City of London, EC2A 2FJ |
> | ----------------------------------------------------------------------- |
>
> On Tue, May 26, 2026 at 2:32 PM Emanuele Nardo <insights@apidae.digital> wrote:
>
>> Hi Josh,
>>
>> Following our conversation, we've successfully verified connectivity and credentials to Cubeia's MySQL replica. Here are all the details you need to set up the OpenFlow PoC.
>>
>> **MySQL Instance**
>>
>> * Engine: MySQL 8.0.42
>> * Host: `<a href="http://betpanda.cov33w6mbrsf.eu-west-1.rds.amazonaws.com/" target="_blank" data-saferedirecturl="https://www.google.com/url?q=http://betpanda.cov33w6mbrsf.eu-west-1.rds.amazonaws.com&source=gmail&ust=1780043734534000&usg=AOvVaw3vqlpku_wcg-SYvhGg47g_"><span class="il">betpanda</span>.cov33w6mbrsf.<wbr/>eu-west-1.rds.amazonaws.com</a>`
>> * Port: 3306
>> * User: `repl_dw_readonly`
>> * Password: *(will share via secure channel)*
>> * SSL: required
>> * Binlog format: ROW
>> * Binlog row image: FULL
>>
>> Confirmed grants on replication user:
>>
>> ```
>> GRANT SELECT, REPLICATION SLAVE, REPLICATION CLIENT ON *.* TO `repl_dw_readonly`@`%`
>> ```
>>
>> **
>> Network connectivity**
>>
>> Cubeia expose the database via AWS PrivateLink. The endpoint service is:
>> `com.amazonaws.vpce.eu-west-1.<wbr/>vpce-svc-0f3c10fa694656a8c` (eu-west-1)
>>
>> We've created our own VPC endpoint for testing purposes, but OpenFlow will need its own network path from Snowflake's infrastructure. Please clarify the preferred approach so we can communicate it to them — either:
>>
>> * Cubeia accepts a PrivateLink connection request from Snowflake's AWS account
>> * Or Snowflake provides source IP ranges to whitelist on their RDS security group
>>
>> **Database scope**
>>
>> 540 tables across 13 schemas. For the PoC we recommend scoping to the following representative tables covering different velocity profiles:
>>
>> | Table                | Schema        | ~Rows | Profile         |
>> | -------------------- | ------------- | ----- | --------------- |
>> | `Transaction`      | nano_wallet   | 1.2B  | High velocity   |
>> | `GameEvent`        | nano_core     | 117M  | High velocity   |
>> | `Payment`          | nano_payments | 5.4M  | Medium velocity |
>> | `user`             | nano_core     | 306K  | Medium velocity |
>> | `fiatcurrencyrate` | nano_exchange | 168   | Low velocity    |
>>
>> Scale concern — please address before the PoC
>>
>> The `nano_wallet` schema contains extremely large tables — `TransactionAttribute` alone is ~9 billion rows. We have three specific questions before proceeding:
>>
>> 1. How does OpenFlow handle the initial snapshot load for tables at this scale? What is the expected duration and compute cost?
>> 2. With this data volume, what warehouse size do you recommend to keep MERGE execution within the 2-minute latency target?
>> 3. Can the initial snapshot be scoped to specific tables to avoid loading Metabase and CMS schemas (which are irrelevant for this PoC)?
>>
>> **Snowflake target**
>>
>> We're planning to provision the Snowflake account in AWS_EU_CENTRAL_1 to align with Vicetech's region. Before we proceed — will you be setting up and running the PoC on your side, or do you need us to provision the target account and infrastructure? Happy to do either, just want to avoid duplication.
>>
>> Looking forward to seeing the results — let us know if anything else is needed on our end.
>>
>> Thanks,
>> Emanuele
>>
>> On Wed, 20 May 2026 at 10:44, Emanuele Nardo <insights@apidae.digital> wrote:
>>
>>> Hi Josh,thanks a lot for the technical explanations above.
>>>
>>> We're good to go for a session today. One thing to flag upfront — we're still resolving a network connectivity issue on Cubeia's side, so the MySQL replica isn't accessible for OpenFlow to connect to just yet.
>>>
>>> That said, we'd still find it very useful to run through the OpenFlow setup together and there's one key question we need to clarify:how does OpenFlow connect to a PrivateLink endpoint service? Cubeia has exposed their MySQL via a VPC endpoint service (com.amazonaws.vpce.eu-west-1.vpce-svc-0f3c10fa694656a8c) Does OpenFlow support creating its own endpoint from Snowflake's infrastructure, or is there another recommended connectivity model?Best regards,Emanuele
>>>
>>> On Tue, 19 May 2026 at 20:09, Josh Lilien [[josh.lilien@snowflake.com](mailto:josh.lilien@snowflake.com)](%5Bjosh.lilien@snowflake.com%5D(mailto:josh.lilien@snowflake.com)) wrote:
>>>
>>>> Sorry, questionnaire attached. Please fill it out at your earliest and we can discuss.
>>>>
>>>> On Tue, May 19, 2026 at 8:09 PM Josh Lilien [[josh.lilien@snowflake.com](mailto:josh.lilien@snowflake.com)](%5Bjosh.lilien@snowflake.com%5D(mailto:josh.lilien@snowflake.com)) wrote:
>>>>
>>>>> Hi Jonathan,
>>>>>
>>>>> As per our conversation earlier, please find the commercial sizing questionnaire attached, which will give us an indication of your credit requirements for the first 1,2 and 3 years.
>>>>>
>>>>> Basically the full process from our end is as follows:1. Tech validation: Address any outstanding tech questions (if applicable) to formally confirm we are the “vendor of choice”2. Commercial options with your leadership or finance team.3. Legal review of our paperwork4. Infosec review (if applicable)5. Contracting discussion (AWS Marketplace, reseller?)6. Implementation + training/enablement plan7. Contract signature and go live8. Ongoing support, account management, health checks etc.
>>>>>
>>>>> For payment options, you basically commit to a certain amount of capacity up front, and then choose:
>>>>>
>>>>> * Contract term: 12, 24 or 36 months
>>>>> * Payment frequency: Annual, semi-annual, or quarterly (annual offers better discounts, of course)
>>>>>
>>>>> Depending on your pace, we can proceed quickly and look to get your production account up and running in June. 
>>>>>
>>>>> Happy to discuss this further tomorrow.
>>>>>
>>>>> Thank you,
>>>>>
>>>>> Josh
>>>>>
>>>>> On Tue, May 19, 2026 at 10:39 AM [[jonathan@bamboom.io](mailto:jonathan@bamboom.io)](%5Bjonathan@bamboom.io%5D(mailto:jonathan@bamboom.io)) wrote:
>>>>>
>>>>>> Thanks for the call Josh,
>>>>>>
>>>>>> Monday works well for me, let me know the time and place that suits you.
>>>>>>
>>>>>> Regards
>>>>>>
>>>>>> Jonathan
>>>>>>
>>>>>> On Monday, 18 May 2026 at 16:30, Josh Lilien [[josh.lilien@snowflake.com](mailto:josh.lilien@snowflake.com)](%5Bjosh.lilien@snowflake.com%5D(mailto:josh.lilien@snowflake.com)) wrote:
>>>>>>
>>>>>>> Understood, thank you Jonathan. Will get this countersigned on my end.
>>>>>>>
>>>>>>> Emanuele, we are all based in London, and also in Malta in every few weeks (despite my accent!!)
>>>>>>>
>>>>>>> Would you both be available for lunch on Monday or Tuesday by chance? Be good to meet before the chaos of Next.io!
>>>>>>>
>>>>>>> Thank you,
>>>>>>>
>>>>>>> Josh
>>>>>>>
>>>>>>> On Mon, May 18, 2026 at 3:20 PM [[jonathan@bamboom.io](mailto:jonathan@bamboom.io)](%5Bjonathan@bamboom.io%5D(mailto:jonathan@bamboom.io)) wrote:
>>>>>>>
>>>>>>>> Hi Josh
>>>>>>>>
>>>>>>>> Please find the NDA signed from our end. Again, we 're waiting the setup on the MySQL instance for the realtime poc.
>>>>>>>>
>>>>>>>> Regards
>>>>>>>>
>>>>>>>> Jonathan
>>>>>>>>
>>>>>>>> On Monday, 18 May 2026 at 11:55, Emanuele Nardo <insights@apidae.digital> wrote:
>>>>>>>>
>>>>>>>>> Hi Josh,
>>>>>>>>>
>>>>>>>>> Great — let's go ahead with the PoC and SME call. We're chasing Cubeia for the MySQL host details and should have access in time, assuming they come back to us shortly.
>>>>>>>>>
>>>>>>>>> For the session we'd like to cover three things:
>>>>>>>>>
>>>>>>>>> 1. Latency validation — measure end-to-end time from MySQL commit to queryable row in the Raw layer, validating against our sub-2-minute requirement
>>>>>>>>> 2. Schema evolution — simulate adding a new column to a source table mid-stream to see how OpenFlow handles the DDL change in practice
>>>>>>>>> 3. MERGE cadence — confirm continuous merge (* * * * * ?) is configured so the destination table reflects changes as fast as possible
>>>>>>>>>
>>>>>>>>> Would Wednesday at 3pm Portugal time (10am ET) work on your end? I assume you guys are based in the US so not considering EU morning time slots.
>>>>>>>>>
>>>>>>>>> Thanks,Emanuele
>>>>>>>>>
>>>>>>>>> On Fri, 15 May 2026 at 18:28, Josh Lilien [[josh.lilien@snowflake.com](mailto:josh.lilien@snowflake.com)](%5Bjosh.lilien@snowflake.com%5D(mailto:josh.lilien@snowflake.com)) wrote:
>>>>>>>>>
>>>>>>>>>> Thanks Emanuele. Is there a convenient time next week to discuss? Tuesday and Wednesday look good.
>>>>>>>>>>
>>>>>>>>>> We can set up the environment and load it with the right number of credits.
>>>>>>>>>>
>>>>>>>>>> Have a good weekend
>>>>>>>>>>
>>>>>>>>>> Josh
>>>>>>>>>>
>>>>>>>>>> | JOSH LILIENAccount Director``MOBILE +44 7826 875 276`` |
>>>>>>>>>> | ------------------------------------------------------------------------- |
>>>>>>>>>>
>>>>>>>>>> | ``![](https://ci3.googleusercontent.com/meips/ADKq_NZTPkwnPcmoWC3Bun64-apwSibVWDW2o-WpPAVuVOWxh7WE8xG4Brj_MAj-VJq4AUYQjDlU1h_ddhm1hxWlD5qQB8WPAn-gVb-rChAlJ5bou64swjwrSfxJl2g4prigEOCoNGvXy_W8HYM=s0-d-e1-ft#https://www.snowflake.com/wp-content/themes/snowflake/img/snowflake-logo-blue@2x.png)`` |
>>>>>>>>>> | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
>>>>>>>>>>
>>>>>>>>>> | Snowflake Inc.``One Crown Place``City of London, EC2A 2FJ |
>>>>>>>>>> | ----------------------------------------------------------------------- |
>>>>>>>>>>
>>>>>>>>>> On Fri, May 15, 2026 at 6:14 PM Emanuele Nardo <insights@apidae.digital> wrote:
>>>>>>>>>>
>>>>>>>>>>> Hi Josh, thanks — very clear answers.
>>>>>>>>>>>
>>>>>>>>>>> Sub-2-minute works for our current requirements, so the OpenFlow approach looks viable.We'd like to validate the exact latency against Cubeia's actual table mix — can we go ahead and schedule the PoC alongside the SME deep-dive you mentioned?
>>>>>>>>>>>
>>>>>>>>>>> On region we'll provision in AWS_EU_CENTRAL_1 to align with ViceTech.
>>>>>>>>>>>
>>>>>>>>>>> Thanks,Emanuele
>>>>>>>>>>>
>>>>>>>>>>> On Fri, 15 May 2026 at 17:48, Matt Lennie [[matt.lennie@snowflake.com](mailto:matt.lennie@snowflake.com)](%5Bmatt.lennie@snowflake.com%5D(mailto:matt.lennie@snowflake.com)) wrote:
>>>>>>>>>>>
>>>>>>>>>>>> Hi Emanuele,
>>>>>>>>>>>>
>>>>>>>>>>>> Thank you for the questions—I will answer each in turn.
>>>>>>>>>>>>
>>>>>>>>>>>> **1. OpenFlow CDC latency (Cubeia)**
>>>>>>>>>>>>
>>>>>>>>>>>> Snowflake doesn't publish a contractual SLA on end-to-end MySQL→Raw latency (from what I can find), but the documented capabilities of the underlying components give a clear picture of what's realistically achievable (hopefully this is sufficient for your requirements? We can schedule a deeper dive with an OpenFlow SME in parallel with this answer if needed.
>>>>>>>>>>>>
>>>>>>>>>>>> OpenFlow's MySQL connector reads directly from the binlog, streams changes via Snowpipe Streaming into an append-only  **journal table** , and then runs a separately scheduled **MERGE** into the destination table. References:
>>>>>>>>>>>>
>>>>>>>>>>>> * [Real-Time CDC at Scale (Snowflake Engineering blog)](https://www.snowflake.com/en/blog/engineering/real-time-change-data-capture-openflow/) — describes the architecture and cites **20,000+ change events per second** throughput.
>>>>>>>>>>>> * [Snowpipe Streaming docs](https://docs.snowflake.com/en/user-guide/snowpipe-streaming/data-load-snowpipe-streaming-overview) — officially states **"as low as 5-second end-to-end ingest-to-query latency"** and **"up to 10 GB/s throughput per table."**
>>>>>>>>>>>>
>>>>>>>>>>>> Putting that together for your sub-2-minute requirement:
>>>>>>>>>>>>
>>>>>>>>>>>> * The **journal table** is queryable within seconds of source commit (Snowpipe Streaming-bounded). If a Live Ops widget needs the absolute freshest data, this is the layer to read from.
>>>>>>>>>>>> * The **destination table** is queryable after the next scheduled MERGE. The merge cadence is fully configurable in the connector ([MySQL connector setup](https://docs.snowflake.com/en/user-guide/data-integration/openflow/connectors/mysql/setup) — "Merge Task Schedule CRON"), with continuous merge (`* * * * * ?`) being the lowest-latency option. With continuous merge, end-to-end source-commit→destination-row time has consistently sat well inside 2 minutes in our internal testing against representative MySQL workloads.
>>>>>>>>>>>>
>>>>>>>>>>>> We recommend validating the exact end-to-end number against Cubeia's specific table mix and change profile in a short joint PoC, but based on the published architecture and our experience, sub-2-minute is a comfortable target rather than an aggressive one.
>>>>>>>>>>>>
>>>>>>>>>>>> **2. Dynamic Tables and the Live Ops Dashboard**
>>>>>>>>>>>>
>>>>>>>>>>>> Two parts here:
>>>>>>>>>>>>
>>>>>>>>>>>> *Which layer should the dashboard query?* For genuinely operational, sub-2-minute use cases we would not point the Live Ops Dashboard at the end of a Raw → Staging → Curated chain. The intent of that chain is to produce well-modelled data for analytical consumption — not to be the lowest-latency path. For live ops we'd recommend either:
>>>>>>>>>>>>
>>>>>>>>>>>> * reading directly from the OpenFlow-landed layer (journal or destination table), or
>>>>>>>>>>>> * a dedicated thin operational model with a short target lag, kept separate from the curated analytical chain.
>>>>>>>>>>>>
>>>>>>>>>>>> *If it did read Curated, how is cumulative lag handled?* Per Snowflake's docs ([Understanding Dynamic Table target lag](https://docs.snowflake.com/en/user-guide/dynamic-tables-target-lag)), target lag is *"a target, not a guarantee"* — actual lag depends on warehouse size, data volume and query complexity, and in a chain it is measured relative to the root tables. So yes, stacking ingestion latency + per-layer DT lag at the operational tier is exactly what we'd avoid, which is why the recommended pattern splits the operational view from the curated analytical view.
>>>>>>>>>>>>
>>>>>>>>>>>> (Note: Dynamic Tables don't impose a 1-minute *minimum* — that's a configuration choice. The relevant point is the cumulative lag in a chain, which is what the architecture should avoid for live ops.)
>>>>>>>>>>>>
>>>>>>>>>>>> **3. Cross-region costs (ViceTech)**
>>>>>>>>>>>>
>>>>>>>>>>>> Short answer: provision your Snowflake account in the same Snowflake region as ViceTech (AWS_EU_CENTRAL_1) and use a Direct Share. That eliminates cross-region replication and egress entirely.
>>>>>>>>>>>>
>>>>>>>>>>>> Per the official docs:
>>>>>>>>>>>>
>>>>>>>>>>>> * A Direct Share works between accounts **in the same region** ([About Secure Data Sharing](https://docs.snowflake.com/en/user-guide/data-sharing-intro)). It is metadata-only and zero-copy — no data movement and therefore no egress.
>>>>>>>>>>>> * Cross-region or cross-cloud sharing requires a Listing with Cross-Cloud Auto-Fulfillment, which physically replicates the share into the target region. This introduces provider-side costs: replication compute, storage in the target region, and data transfer/egress. Mechanics and cost details: [Share data across regions and cloud platforms](https://docs.snowflake.com/en/user-guide/secure-data-sharing-across-regions-platforms) and [Auto-fulfillment costs](https://docs.snowflake.com/en/collaboration/provider-understand-cost-auto-fulfillment).
>>>>>>>>>>>>
>>>>>>>>>>>> Recommendation for minimising both cost and complexity: provision in AWS eu-central-1 alongside ViceTech and use a Direct Share.
>>>>>>>>>>>>
>>>>>>>>>>>> Happy to walk through the target-state design in more detail — particularly which datasets should remain truly operational (served close to the journal layer) and which are better served from curated models.
>>>>>>>>>>>>
>>>>>>>>>>>> --
>>>>>>>>>>>>
>>>>>>>>>>>> | Matt Lennie                                    |
>>>>>>>>>>>> | ---------------------------------------------- |
>>>>>>>>>>>> | Senior Solution consultant                     |
>>>>>>>>>>>> | MOBILE: +44(0)7756 246857                      |
>>>>>>>>>>>> | EMAIL: Matt.Lennie@Snowflake.com`` |
>>>>>>>>>>>>
>>>>>>>>>>>
>>>>>>>>>>
>>>>>>>>>
>>>>>>>>
>>>>>>>
>>>>>>> --
>>>>>>>
>>>>>>> | JOSH LILIENAccount Director``MOBILE +44 7826 875 276`` |
>>>>>>> | ------------------------------------------------------------------------- |
>>>>>>>
>>>>>>> | ``![](https://ci3.googleusercontent.com/meips/ADKq_NZTPkwnPcmoWC3Bun64-apwSibVWDW2o-WpPAVuVOWxh7WE8xG4Brj_MAj-VJq4AUYQjDlU1h_ddhm1hxWlD5qQB8WPAn-gVb-rChAlJ5bou64swjwrSfxJl2g4prigEOCoNGvXy_W8HYM=s0-d-e1-ft#https://www.snowflake.com/wp-content/themes/snowflake/img/snowflake-logo-blue@2x.png)`` |
>>>>>>> | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
>>>>>>>
>>>>>>> | Snowflake Inc.``One Crown Place``City of London, EC2A 2FJ |
>>>>>>> | ----------------------------------------------------------------------- |
>>>>>>>
>>>>>>
>>>>>
>>>>> --JOSH LILIENAccount DirectorMOBILE  +44 7826 875 276Snowflake Inc.One Crown PlaceCity of London, EC2A 2FJ
>>>>>
>>>>
>>>> --JOSH LILIENAccount DirectorMOBILE  +44 7826 875 276Snowflake Inc.One Crown PlaceCity of London, EC2A 2FJ
>>>>
>>>
>>

<iframe src="https://meet.google.com/call?authuser=0&hl=en&mc=KAIwAZoBFDoScGludG9fNGQ0a3Y0ZDd1OHZxogE7GgIQADICUAA6AhABSgQIARABWgIIAGoCCAFyAggBegIIAogBAJIBAhABmgEEGAEgAKIBAhAA4gECCACyAQcYAyAAKgEwwgECIAHYAQE&origin=https%3A%2F%2Fmail.google.com&iilm=1779956474380" allow="autoplay;camera;compute-pressure;display-capture;fullscreen;microphone;screen-wake-lock;speaker;hid" name="pip_frame" aria-label="Picture-in-picture mode." title="Google Meet" tabindex="0" class="smzcOb ES1Rtb" data-connected="true"></iframe>

1Password menu is available. Press down arrow to select.

bethlyons1123@gmail.com. Press tab to insert.
