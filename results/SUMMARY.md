# Luxor vs AntPool live Stratum comparison

- Verdict: **CONSISTENT WITH INDEPENDENT TEMPLATES during this observation window.**
- Duration: 425.159 seconds
- Luxor jobs: 1
- AntPool jobs: 15
- Paired comparisons: 1
- Mean weighted similarity: 0.0623779296875
- Median weighted similarity: 0.0623779296875
- Similarity range: 0.0623779296875 to 0.0623779296875
- Identical branch-list pairs: 0

The score uses 0xB10C's published weighting, where later Merkle branches carry more weight.
This verdict applies only to the tested endpoints and observation window.

## Diagnostics

~~~json
{
  "luxor": {
    "responses": [
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
              "00008a8a1"
            ],
            [
              "mining.set_difficulty",
              "00008a8a2"
            ]
          ],
          "00008a8a",
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
