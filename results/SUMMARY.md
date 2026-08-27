# Braiins vs AntPool live Stratum comparison

- Verdict: **CONSISTENT WITH INDEPENDENT TEMPLATES during this observation window.**
- Duration: 423.447 seconds
- Braiins jobs: 16
- AntPool jobs: 15
- Paired comparisons: 16
- Mean weighted similarity: 0.005645751953125
- Median weighted similarity: 0.0035400390625
- Similarity range: 0.000732421875 to 0.015380859375
- Identical branch-list pairs: 0

The score uses 0xB10C's published weighting, where later Merkle branches carry more weight.
This verdict applies only to the tested endpoints and observation window.

## Diagnostics

~~~json
{
  "braiins": {
    "responses": [
      {
        "id": 1,
        "result": [
          [
            [
              "mining.set_difficulty",
              "1"
            ],
            [
              "mining.notify",
              "1"
            ]
          ],
          "",
          6
        ],
        "error": null
      },
      {
        "id": 2,
        "result": false,
        "error": null
      },
      {
        "id": null,
        "method": "mining.set_difficulty",
        "params": [
          8192
        ]
      },
      {
        "id": null,
        "method": "mining.set_difficulty",
        "params": [
          2048
        ]
      },
      {
        "id": null,
        "method": "mining.set_difficulty",
        "params": [
          1024
        ]
      }
    ],
    "errors": []
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
              "0000fca21"
            ],
            [
              "mining.set_difficulty",
              "0000fca22"
            ]
          ],
          "0000fca2",
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
