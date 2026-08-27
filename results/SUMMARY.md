# Luxor vs AntPool live Stratum comparison

- Verdict: **PARTIAL/AMBIGUOUS SIMILARITY: longer sampling and branch-position analysis are required.**
- Duration: 420.707 seconds
- Luxor jobs: 1
- AntPool jobs: 15
- Paired comparisons: 1
- Mean weighted similarity: 0.249755859375
- Median weighted similarity: 0.249755859375
- Similarity range: 0.249755859375 to 0.249755859375
- Identical branch-list pairs: 0

The score uses 0xB10C's published weighting, where later Merkle branches carry more weight.
This verdict applies only to the tested endpoints and observation window.

## Diagnostics

~~~json
{
  "luxor": {
    "responses": [
      {
        "id": 1,
        "result": [
          [
            [
              "mining.notify",
              "00"
            ],
            [
              "mining.set_difficulty",
              "00"
            ]
          ],
          "00",
          7
        ],
        "error": null
      },
      {
        "id": null,
        "method": "mining.set_difficulty",
        "params": [
          65536
        ]
      },
      {
        "id": 2,
        "result": false,
        "error": [
          24,
          "not authorized: publicobserver.worker",
          null
        ]
      },
      {
        "id": null,
        "method": "mining.set_difficulty",
        "params": [
          16384
        ]
      }
    ],
    "errors": [
      "ConnectionResetError: [Errno 104] Connection reset by peer"
    ]
  },
  "antpool": {
    "responses": [
      {
        "error": null,
        "id": 1,
        "result": [
          [
            [
              "mining.notify",
              "000071c61"
            ],
            [
              "mining.set_difficulty",
              "000071c62"
            ]
          ],
          "000071c6",
          8
        ]
      },
      {
        "error": null,
        "id": 2,
        "result": true
      },
      {
        "id": null,
        "method": "mining.set_difficulty",
        "params": [
          65536
        ]
      },
      {
        "id": null,
        "method": "mining.set_difficulty",
        "params": [
          16384
        ]
      }
    ],
    "errors": []
  }
}
~~~
